"""D1b — build a possession/stint CHALLENGER run from the V3 linked events.

Separately versioned from the incumbent (infer_possessions.py ->
possessions_by_season/ -> rapm_stints_by_season/, which the nba_value DAG still
uses). This never writes into silver: it writes an immutable run directory under
--out-root that a reviewer can reconcile before any RAPM refit uses it.

Pipeline (scripts/nba_value/data/possession_ledger.py):
  sealed inputs -> normalize_events -> scoring_ledger (reconcile to box; games that
  fail are QUARANTINED with reasons, never dropped silently) -> reconstruct_possessions
  -> build_stints (+ exclusions) -> game_accounting_rows -> the D1 release predicate
  (audit_rapm_exposure_units.game_accounting / season_release) against the cohort.

Cohort: --games <ids> (the audited cohort first), else every regular-season game of
--season with both teams in the box record.

  <out-root>/<RUN_ID>/
      game_status.parquet  scoring_events.parquet  possessions.parquet
      segments.parquet  stints.parquet  exclusions.parquet  game_accounting.parquet
      manifest.json

Usage:
  python scripts/nba_value/data/build_possession_challenger.py --season 2023-24 \
      --games 0022300640 0022300214 --out-root <scratch>/possessions
  python scripts/nba_value/data/build_possession_challenger.py --season 2023-24 --out-root <scratch> --enforce
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api.src.ml.io.atomic_io import write_json_atomic, write_parquet_atomic
from scripts.nba_value.analysis.audit_rapm_exposure_units import (
    EXCLUSION_POLICIES,
    PASSING_RELEASE,
    game_accounting,
    season_release,
)
from scripts.nba_value.data import link_pbp_vectorized as linker
from scripts.nba_value.data import possession_ledger as ledger
from scripts.nba_value.data.link_pbp_to_stints import parse_clock_to_seconds

DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"
PBP_BRONZE_ROOT = PROJECT_ROOT / "data" / "bronze" / "nba" / "play_by_play"
CODE_PATHS = [Path(__file__).resolve(), Path(ledger.__file__).resolve(),
              PROJECT_ROOT / "scripts" / "nba_value" / "analysis" / "audit_rapm_exposure_units.py"]
REGULAR_SEASON_PREFIX = "002"
OUTPUTS = ["game_status", "scoring_events", "possessions", "segments", "stints",
           "exclusions", "game_accounting", "excluded_possessions", "excluded_events"]
# Event columns sealed for games removed by an alternation policy.
EXCLUDED_EVENT_COLUMNS = ["GAME_ID", "SEQ", "PERIOD", "ELAPSED", "ACTION", "TEAM_ID", "PERSON_ID",
                          "ORDER_NUMBER", "ORDER_INVERSION"]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gid(s: pd.Series) -> pd.Series:
    return s.astype(str).str.zfill(10)


def read_sealed(paths: dict) -> tuple[dict, dict]:
    frames, seals = {}, {}
    for name, path in paths.items():
        data = Path(path).read_bytes()
        frames[name] = pd.read_parquet(io.BytesIO(data))
        seals[name] = {"path": str(path), "sha256": _sha(data), "rows": len(frames[name])}
    return frames, seals


def game_teams_from_box(team_game: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Real home/away from the box record ("TEAM vs. OPP" is home). A game without
    exactly one home and one away team row is excluded from the cohort."""
    tg = team_game.copy()
    tg["GAME_ID"] = _gid(tg["GAME_ID"])
    tg = tg[tg["GAME_ID"].str.startswith(REGULAR_SEASON_PREFIX)]
    tg["IS_HOME"] = tg["MATCHUP"].str.contains(" vs. ", regex=False)
    counts = tg.groupby("GAME_ID")["IS_HOME"].agg(["size", "sum"])
    ok = counts[(counts["size"] == 2) & (counts["sum"] == 1)].index
    tg = tg[tg["GAME_ID"].isin(ok)]
    home = tg[tg["IS_HOME"]].set_index("GAME_ID")
    away = tg[~tg["IS_HOME"]].set_index("GAME_ID")
    game_teams = pd.DataFrame({"HOME_TEAM_ID": home["TEAM_ID"], "AWAY_TEAM_ID": away["TEAM_ID"],
                               "SEASON_ID": home["SEASON_ID"]}).rename_axis("GAME_ID").reset_index()
    box = pd.DataFrame({"HOME_PTS": home["PTS"], "AWAY_PTS": away["PTS"]}).rename_axis("GAME_ID").reset_index()
    return game_teams, box


def link_from_bronze(cohort: set, season: str, bronze_root: Path, rotation: pd.DataFrame) -> tuple:
    """Link each cohort game straight from its bronze PBP file with the existing
    linker (link_game_vectorized, unchanged). The cached linked_events_by_season
    files are stale (2023-24: 121 of 122 absent games link today), and the season
    loop that builds them swallows per-game exceptions. Here every failure is a
    named per-game quarantine reason, and every bronze file is hashed."""
    rot = rotation.copy()
    rot["GAME_ID"] = _gid(rot["GAME_ID"])
    by_game = {g: grp for g, grp in rot[rot["GAME_ID"].isin(cohort)].groupby("GAME_ID")}
    frames, seals, failures = [], {}, {}
    for gid in sorted(cohort):
        path = bronze_root / season / "games" / f"{gid}.json.gz"
        if not path.exists():
            failures[gid] = "no_bronze_pbp"
            continue
        data = path.read_bytes()
        seals[f"bronze/{gid}"] = {"path": str(path), "sha256": _sha(data)}
        try:
            pbp = pd.DataFrame(json.loads(gzip.decompress(data))["data"])
            pbp = linker._normalize_cdn_taxonomy(pbp)
            pbp["event_time"] = [parse_clock_to_seconds(c, p) for c, p in zip(pbp["clock"], pbp["period"])]
            linked = linker.link_game_vectorized(pbp, by_game.get(gid, pd.DataFrame()), gid)
        # Malformed-game data errors become a named quarantine; anything else raises.
        except (KeyError, ValueError, IndexError, TypeError, OSError) as exc:
            failures[gid] = f"link_failed: {type(exc).__name__}: {str(exc)[:120]}"
            continue
        if len(linked) == 0:
            failures[gid] = "link_empty"
            continue
        frames.append(linked)
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return events, seals, failures


def build(season: str, out_root: Path, data_root: Path = DATA_ROOT, games: list | None = None,
          events_source: str = "bronze", bronze_root: Path = PBP_BRONZE_ROOT,
          exclude: dict | None = None) -> Path:
    sup = data_root / "silver" / "nba" / "supplements"
    paths = {"team_game_fact": data_root / "silver" / "nba" / "facts" / "team_game_fact.parquet",
             "game_rotation_player_stint": sup / "game_rotation_player_stint.parquet"}
    if events_source == "linked":
        paths["linked_events"] = sup / "linked_events_by_season" / f"{season}.parquet"
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Challenger inputs missing: {missing}")
    frames, seals = read_sealed(paths)
    game_teams, box = game_teams_from_box(frames["team_game_fact"])
    season_games = set(game_teams.loc[game_teams["SEASON_ID"] == season, "GAME_ID"])
    cohort = set(games) if games else season_games
    unknown = sorted(cohort - season_games)
    if unknown:
        raise ValueError(f"Cohort games not in the {season} box cohort: {unknown[:5]}")

    if events_source == "bronze":
        events, bronze_seals, source_failures = link_from_bronze(
            cohort, season, bronze_root, frames["game_rotation_player_stint"])
        seals.update(bronze_seals)
    else:
        events = frames["linked_events"]
        events = events[_gid(events["gameId"]).isin(cohort)]
        source_failures = {}
    present = set(_gid(events["gameId"])) if len(events) else set()
    for gid in cohort - present - set(source_failures):
        source_failures[gid] = "no_events_in_source"

    # Identity covers every sealed byte (incl. each bronze file), the code, the
    # cohort and the event source; computed only after all inputs are read.
    code_sha = _sha(b"".join(_sha(p.read_bytes()).encode() for p in CODE_PATHS))
    cohort_key = ",".join(sorted(games)) if games else f"season:{season}"
    ident = "|".join(f"{k}:{v['sha256']}" for k, v in sorted(seals.items()))
    exclude = exclude or {}
    excl_key = ",".join(f"{g}={r}" for g, r in sorted(exclude.items()))
    run_id = _sha(f"{ident}|code:{code_sha}|cohort:{cohort_key}|source:{events_source}"
                  f"|exclude:{excl_key}".encode())[:16]
    run_dir = out_root / run_id
    if (run_dir / "manifest.json").exists():
        _verify(run_dir)
        print(f"Run {run_id} already exists (same sealed inputs/code/cohort) — verified, not rewritten.")
        return run_dir
    if run_dir.exists():
        raise RuntimeError(f"{run_dir} exists without a manifest: an incomplete run; inspect it, never overwrite")

    rot = frames["game_rotation_player_stint"][["GAME_ID", "PLAYER_ID", "TEAM_ID"]].copy()
    rot["GAME_ID"] = _gid(rot["GAME_ID"])
    player_team = rot[rot["GAME_ID"].isin(cohort)].drop_duplicates(["GAME_ID", "PLAYER_ID"])
    gt = game_teams[game_teams["GAME_ID"].isin(cohort)]

    norm = ledger.normalize_events(events, gt, player_team)
    scoring_events, status = ledger.scoring_ledger(norm, box[box["GAME_ID"].isin(cohort)])
    if source_failures:   # every cohort game ends with a status: no game disappears
        status = pd.concat([status, pd.DataFrame(
            {"GAME_ID": list(source_failures), "STATUS": "QUARANTINED",
             "REASON": list(source_failures.values())})], ignore_index=True)
    admitted = set(status.loc[status["STATUS"] == "ADMITTED", "GAME_ID"])
    possessions, segments = ledger.reconstruct_possessions(norm[norm["GAME_ID"].isin(admitted)])
    # Possession alternation: a game with a period where one team has 2+ more
    # possessions leaves the model inputs WHOLE -- never repaired with a guessed
    # order or a synthesized possession -- as source_order_unresolvable (policy
    # source-order-v1), source_possession_unlogged (policy source-absence-v2) or
    # possession_alternation_unexplained (anything else; a parser gap).
    schema = "live" if "orderNumber" in events.columns else "legacy"
    inversions = norm.groupby(["GAME_ID", "PERIOD"])["ORDER_INVERSION"].sum()
    repeats = ledger.same_team_repeats(possessions, norm, player_team)
    alternation = ledger.classify_alternation_failures(possessions, inversions, schema, repeats)
    reconstructed = set(possessions["GAME_ID"])
    # The removed games' possessions and event rows are sealed so the gate re-derives
    # each alternation exclusion's evidence itself.
    excluded_possessions = possessions[possessions["GAME_ID"].isin(alternation)].reset_index(drop=True)
    removed_rows = norm[norm["GAME_ID"].isin(alternation)]
    excluded_events = removed_rows[EXCLUDED_EVENT_COLUMNS].assign(
        PERSON_TEAM_ID=ledger.person_team_ids(removed_rows, player_team)).reset_index(drop=True)
    if alternation:
        possessions = possessions[~possessions["GAME_ID"].isin(alternation)].reset_index(drop=True)
        segments = segments[~segments["GAME_ID"].isin(alternation)].reset_index(drop=True)
        hit = status["GAME_ID"].isin(alternation)
        status.loc[hit, "STATUS"] = "QUARANTINED"
        status.loc[hit, "REASON"] = status.loc[hit, "GAME_ID"].map(alternation)
        admitted -= set(alternation)
    # Sealed evidence for every game, re-checked independently by the SQL gate.
    status["ORDER_INVERSIONS"] = status["GAME_ID"].map(
        norm.groupby("GAME_ID")["ORDER_INVERSION"].sum()).astype("Int64")
    status["EVENT_SCHEMA"] = schema
    # Diagnostics for every reconstructed game: same-team repeats (a possession
    # boundary the source or the parser lost; admitted games can carry them within
    # the +-1 alternation bound) and the subset verified as source absence.
    verified = repeats[repeats["VERIFIED"].astype(bool)].groupby("GAME_ID").size()
    every = repeats.groupby("GAME_ID").size()
    for col, counts in (("SAME_TEAM_REPEATS", every), ("UNLOGGED_POSSESSION_GAPS", verified)):
        status[col] = pd.array([int(counts.get(g, 0)) if g in reconstructed else pd.NA
                                for g in status["GAME_ID"]], dtype="Int64")
    stints, exclusions = ledger.build_stints(segments, gt, season)
    # Periods played come from this run's own events (periods with a real event),
    # not the rotation feed's game length, which is unknown for some games.
    played = norm[norm["ACTION"] != "period"]
    periods = played.groupby("GAME_ID")["PERIOD"].nunique().astype(float)
    acc = game_accounting(ledger.game_accounting_rows(possessions, gt, box, periods, season))
    # A declared exclusion is checked against the reason this run actually recorded.
    actual = dict(zip(status["GAME_ID"], status["REASON"]))
    declared = {g: {"declared": r, "actual": actual.get(g)} for g, r in exclude.items()}
    release = season_release(acc, {season: cohort}, exclusions=declared)[season]

    outputs = {"game_status": status, "scoring_events": scoring_events, "possessions": possessions,
               "segments": _listify(segments), "stints": stints, "exclusions": exclusions,
               "game_accounting": acc, "excluded_possessions": excluded_possessions,
               "excluded_events": excluded_events}
    tmp = out_root / f".{run_id}.partial-{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=False)
    for name, df in outputs.items():
        write_parquet_atomic(df, tmp / f"{name}.parquet", index=False)
    ft_kinds = norm.loc[norm["ACTION"] == "free_throw", "FT_KIND"].value_counts().to_dict()
    manifest = {
        "product": "possession_challenger", "run_id": run_id, "season": season,
        "cohort": sorted(cohort), "cohort_kind": "explicit" if games else "season_box_cohort",
        "events_source": events_source, "event_schema": schema,
        "exclusion_policies": EXCLUSION_POLICIES,
        "declared_exclusions": declared,
        "created_at_utc": datetime.now(UTC).isoformat(), "inputs": seals, "code_sha256": code_sha,
        "games": {"cohort": len(cohort), "events_present": int(norm["GAME_ID"].nunique()),
                  "admitted": len(admitted), "quarantined": int((status["STATUS"] != "ADMITTED").sum())},
        "quarantine_reasons": status.loc[status["STATUS"] != "ADMITTED", "REASON"].value_counts().to_dict(),
        "free_throw_kinds": {str(k): int(v) for k, v in ft_kinds.items()},
        "free_throw_outcome_sources": {str(k): int(v) for k, v in norm.loc[
            norm["ACTION"] == "free_throw", "FT_OUTCOME_SOURCE"].value_counts(dropna=False).items()},
        "possessions": len(possessions),
        "unattributed_possessions": int(possessions["OFFENSE_TEAM_ID"].isna().sum()),
        "excluded_possessions": float(exclusions["EXCLUDED_POSS"].sum()) if len(exclusions) else 0.0,
        "release": release,
        "files": {f"{n}.parquet": _sha((tmp / f"{n}.parquet").read_bytes()) for n in outputs},
    }
    write_json_atomic(manifest, tmp / "manifest.json", indent=2)
    try:
        os.rename(tmp, run_dir)
    except OSError:
        if not (run_dir / "manifest.json").exists():
            raise
        shutil.rmtree(tmp)
        _verify(run_dir)
    print(f"Wrote possession challenger {run_id}: {manifest['games']} release={release['status']} -> {run_dir}")
    return run_dir


def _listify(segments: pd.DataFrame) -> pd.DataFrame:
    """Parquet stores lineups as lists; tuples are an in-memory convenience."""
    s = segments.copy()
    for col in ("HOME_ON", "AWAY_ON"):
        s[col] = s[col].map(lambda t: list(t) if t is not None else None)
    return s


def _verify(run_dir: Path) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        actual = _sha((run_dir / name).read_bytes())
        if actual != expected:
            raise RuntimeError(f"Existing run {run_dir.name}/{name} sha256 {actual} != manifest {expected}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", required=True)
    ap.add_argument("--games", nargs="*", help="explicit cohort (GAME_IDs); default: the season box cohort")
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--out-root", type=Path, required=True, help="scratch directory; never silver")
    ap.add_argument("--enforce", action="store_true", help="exit 3 unless the release predicate passes")
    ap.add_argument("--events-source", choices=["bronze", "linked"], default="bronze",
                    help="bronze: link each game from its PBP file (default); linked: the cached "
                         "linked_events_by_season file (stale for 2023-24)")
    ap.add_argument("--bronze-root", type=Path, default=PBP_BRONZE_ROOT)
    ap.add_argument("--exclude", action="append", default=[], metavar="GAME_ID=REASON",
                    help="declare a source-absence exclusion; accepted only if REASON is the "
                         "game's actual quarantine reason and a source-absence reason")
    args = ap.parse_args()
    games = [g.zfill(10) for g in args.games] if args.games else None
    exclude = dict(item.split("=", 1) for item in args.exclude)
    exclude = {g.zfill(10): r for g, r in exclude.items()}
    run_dir = build(args.season, args.out_root.resolve(), args.data_root.resolve(), games,
                    args.events_source, args.bronze_root.resolve(), exclude)
    release = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["release"]
    return 3 if args.enforce and release["status"] not in PASSING_RELEASE else 0


if __name__ == "__main__":
    raise SystemExit(main())
