"""Point-in-time (pregame) corrected RAPM on the D1b possession challenger's stints.

Estimator `betts.rapm.corrected_possessions.pregame.v1`: the past-only counterpart of
the retrospective `betts.rapm.corrected_possessions.v2`. A rating issued at date `t`
may use ONLY evidence available strictly before `t` -- no leakage from games that
have not been played yet at issuance time.

Issuance schedule: for target season S, ratings are issued on the season's first
game date and every `--cadence-days` after it, through the season's last game date.
A rating issued at `t` is fit on releasable stints from up to two prior seasons
(S-1, S-2 -- whichever are provided) at full weight (per-season decay exactly as
v2: target 1.0, S-1 0.8, S-2 0.64, via `build_multi_season_matrix` with
`target_season=S`) plus target-season stints from games dated strictly before `t`.
The min-possessions-per-stint filter is applied once per pooled season (not
per-issuance), same as v2.

Lambda is frozen and past-only: it is read from the retrospective v2 fit manifest
for season S-1 (`--lambda-from`), which must carry
`estimator_id == betts.rapm.corrected_possessions.v2` and `target_season == S-1` --
using any other lambda would leak information about S that was not available at
any pregame issuance. Because the earliest v2 fit is for 2015-16, pregame starts at
target season 2016-17.

  <out-root>/<RUN_ID>/rapm_pregame.parquet, manifest.json

Usage:
  python scripts/nba_value/calibration/fit_rapm_pregame.py --target-season 2017-18 \\
      --run 2016-17=<release run dir> --run 2017-18=<release run dir> \\
      --lambda-from <v2 fit dir for 2016-17> --out-root <scratch>
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.linear_model import Ridge

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api.src.ml.features.rapm_pipeline.design_matrix import build_multi_season_matrix
from api.src.ml.io.atomic_io import write_json_atomic, write_parquet_atomic
from scripts.nba_value.calibration.fit_rapm_corrected import (
    ESTIMATOR_ID as V2_ESTIMATOR_ID,
)
from scripts.nba_value.calibration.fit_rapm_corrected import (
    filter_min_possessions,
    load_releasable_run,
)

ESTIMATOR_ID = "betts.rapm.corrected_possessions.pregame.v1"
DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prior_season(season: str) -> str:
    """S-1 given S, e.g. '2016-17' -> '2015-16'."""
    start = int(season[:4])
    return f"{start - 1}-{start % 100:02d}"


def issuance_dates(first_game_date, last_game_date, cadence_days: int) -> list[pd.Timestamp]:
    """The season's first game date, then every `cadence_days` after it, through the
    last game date (never past it -- the last issuance may fall short of the finale)."""
    if cadence_days <= 0:
        raise ValueError(f"cadence_days must be a positive number of days, got {cadence_days}")
    first_game_date, last_game_date = pd.Timestamp(first_game_date), pd.Timestamp(last_game_date)
    if last_game_date < first_game_date:
        raise ValueError(f"last_game_date {last_game_date} is before first_game_date {first_game_date}")
    step = pd.Timedelta(days=cadence_days)
    dates, t = [], first_game_date
    while t <= last_game_date:
        dates.append(t)
        t += step
    return dates


def guard_no_future_stints(stints: pd.DataFrame, dates: pd.Series, cutoff) -> None:
    """Refuse to fit on any stint whose game date is missing or on/after `cutoff` --
    the pregame estimator's core no-leakage invariant, checked immediately before
    every fit against the exact pooled training set used for that fit."""
    game_dates = stints["game_id"].map(dates)
    if game_dates.isna().any():
        missing = sorted(stints.loc[game_dates.isna(), "game_id"].unique())[:5]
        raise ValueError(f"training stints with no resolvable GAME_DATE (cannot verify the "
                         f"pregame cutoff {cutoff}): {missing}")
    leaked = game_dates >= cutoff
    if leaked.any():
        bad = sorted(stints.loc[leaked, "game_id"].unique())[:5]
        raise ValueError(f"training stints dated on/after the issuance cutoff {cutoff} "
                         f"would leak the future: {bad}")


def load_frozen_lambda(lambda_from: Path, expected_target_season: str) -> tuple[float, dict]:
    """Read the frozen, past-only lambda from a retrospective v2 fit manifest. Refuses
    unless that fit is exactly for `expected_target_season` (S-1 of the pregame target),
    since any other lambda would leak information not available at pregame issuance."""
    manifest_path = Path(lambda_from) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("estimator_id") != V2_ESTIMATOR_ID:
        raise ValueError(f"{lambda_from}: estimator_id is {manifest.get('estimator_id')!r}, "
                         f"expected {V2_ESTIMATOR_ID!r}")
    if manifest.get("target_season") != expected_target_season:
        raise ValueError(f"{lambda_from}: target_season is {manifest.get('target_season')!r}, "
                         f"expected {expected_target_season!r} (S-1 of the pregame target season)")
    return float(manifest["lambda"]), {"run_id": manifest["run_id"], "manifest_sha256": _sha(manifest_path)}


def _target_playing_time(target_subset: pd.DataFrame) -> pd.DataFrame:
    """Per-player on-court possessions and stint counts within the target-season
    subset actually used for training (i.e. already restricted to before `t`)."""
    lineups = target_subset["home_lineup"].map(list) + target_subset["away_lineup"].map(list)
    return (pd.DataFrame({"PLAYER_ID": lineups, "POSS": target_subset["possessions"].astype(float)})
            .explode("PLAYER_ID").astype({"PLAYER_ID": "int64"}).groupby("PLAYER_ID")
            .agg(TARGET_POSSESSIONS_BEFORE=("POSS", "sum"), N_STINTS_BEFORE=("POSS", "size"))
            .reset_index())


def issue_ratings(season_stints: dict, target: str, decay: float, lam: float,
                  dates: pd.Series, issued_at) -> pd.DataFrame:
    """Fit and rate a single issuance. `season_stints[target]` must already be
    restricted to games dated strictly before `issued_at` by the caller; every other
    pooled season is used at full weight. Rows cover every player present anywhere
    in the pooled training stints, not only those with target-season minutes."""
    combined = pd.concat([season_stints[s] for s in sorted(season_stints)], ignore_index=True)
    guard_no_future_stints(combined, dates, issued_at)

    X, y, w, index = build_multi_season_matrix(season_stints, target, decay)
    model = Ridge(alpha=lam, fit_intercept=True).fit(X, y, sample_weight=w)

    out = pd.DataFrame({"PLAYER_ID": list(index), "RAPM_NET": model.coef_[list(index.values())]})
    playtime = _target_playing_time(season_stints[target])
    out = out.merge(playtime, on="PLAYER_ID", how="left")
    # A player absent from the target-season-before-t subset genuinely has zero
    # on-court possessions there so far this season -- a real count, not missing
    # data (he may still have prior-season stints, which is what earns him a row).
    out["TARGET_POSSESSIONS_BEFORE"] = out["TARGET_POSSESSIONS_BEFORE"].fillna(0.0)  # ALLOWLIST_DEFENSIVE_FILLNA - honest zero on-court count, not absent data
    out["N_STINTS_BEFORE"] = out["N_STINTS_BEFORE"].fillna(0).astype("int64")  # ALLOWLIST_DEFENSIVE_FILLNA - honest zero on-court count, not absent data

    out.insert(0, "ISSUED_AT", issued_at)
    out.insert(1, "SEASON", target)
    out["TRAINING_CUTOFF"] = combined["game_id"].map(dates).max()
    out["LAMBDA"] = lam
    out["ESTIMATOR_ID"] = ESTIMATOR_ID
    out = out[["ISSUED_AT", "SEASON", "PLAYER_ID", "RAPM_NET", "TRAINING_CUTOFF",
              "TARGET_POSSESSIONS_BEFORE", "N_STINTS_BEFORE", "LAMBDA", "ESTIMATOR_ID"]]
    return out.sort_values("PLAYER_ID").reset_index(drop=True)


def build(target: str, runs: dict, lambda_from: Path, out_root: Path, data_root: Path = DATA_ROOT, *,
         cadence_days: int = 7, decay: float = 0.80, min_poss: int = 3) -> Path:
    if target not in runs:
        raise ValueError(f"target season {target} has no run")
    lam, lambda_source = load_frozen_lambda(Path(lambda_from), prior_season(target))

    season_stints, sources, removed = {}, {}, {}
    for season, run_dir in sorted(runs.items()):
        stints, manifest = load_releasable_run(Path(run_dir))
        if manifest["season"] != season:
            raise ValueError(f"{run_dir}: run is for {manifest['season']}, not {season}")
        stints, removed[season] = filter_min_possessions(stints, min_poss)
        season_stints[season] = stints
        sources[season] = {"run_dir": str(run_dir), "run_id": manifest["run_id"],
                           "manifest_sha256": _sha(Path(run_dir) / "manifest.json"),
                           "release": manifest["release"]["status"],
                           "exclusion_policies": manifest["exclusion_policies"]}

    tg = pd.read_parquet(data_root / "silver/nba/facts/team_game_fact.parquet",
                        columns=["GAME_ID", "GAME_DATE", "SEASON_ID"])
    tg = tg.assign(GAME_ID=tg["GAME_ID"].astype(str).str.zfill(10)).drop_duplicates("GAME_ID")
    dates = tg.set_index("GAME_ID")["GAME_DATE"]
    for season, stints in season_stints.items():
        missing = sorted(stints.loc[stints["game_id"].map(dates).isna(), "game_id"].unique())
        if missing:
            raise ValueError(f"{season}: {len(missing)} game(s) missing GAME_DATE, cannot "
                             f"pregame-gate: {missing[:5]}")
    season_games = tg[tg["SEASON_ID"] == target]
    if season_games.empty:
        raise ValueError(f"no games with SEASON_ID={target!r} in {data_root}")
    issued_at_list = issuance_dates(season_games["GAME_DATE"].min(), season_games["GAME_DATE"].max(),
                                    cadence_days)

    prior_full = {s: v for s, v in season_stints.items() if s != target}
    full_target = season_stints[target]
    rows, issuances = [], []
    for t in issued_at_list:
        target_before = full_target[full_target["game_id"].map(dates) < t].reset_index(drop=True)
        pooled = {**prior_full, target: target_before}
        out = issue_ratings(pooled, target, decay, lam, dates, t)
        rows.append(out)
        combined_len = sum(len(v) for v in pooled.values())
        combined_poss = sum(float(v["possessions"].sum()) for v in pooled.values())
        issuances.append({"issued_at": t.isoformat(), "training_stints": combined_len,
                          "training_possessions": combined_poss, "players": len(out),
                          "target_games_before": int(target_before["game_id"].nunique())})

    ratings = pd.concat(rows, ignore_index=True)

    code_sha = _sha(Path(__file__).resolve())
    ident = json.dumps({"sources": {s: v["manifest_sha256"] for s, v in sources.items()},
                        "target": target, "decay": decay, "min_poss": min_poss,
                        "cadence_days": cadence_days, "lambda_source": lambda_source,
                        "code": code_sha}, sort_keys=True)
    run_id = hashlib.sha256(ident.encode()).hexdigest()[:16]
    run_dir = out_root / run_id
    if (run_dir / "manifest.json").exists():
        print(f"RAPM pregame run {run_id} already exists -- not rewritten.")
        return run_dir
    tmp = out_root / f".{run_id}.partial-{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=False)
    write_parquet_atomic(ratings, tmp / "rapm_pregame.parquet", index=False)
    manifest = {
        "product": "rapm_pregame", "estimator_id": ESTIMATOR_ID, "run_id": run_id,
        "target_season": target, "cadence_days": cadence_days,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "rate_unit": "net points per 100 combined (both-team) possessions, challenger possessions",
        "construction": "raw targets (not luck adjusted); ridge with intercept; real home frame; "
                       "past-only issuance (pregame)",
        "pooled_seasons": sorted(season_stints), "decay": decay, "min_poss_per_stint": min_poss,
        "lambda": lam, "lambda_frozen": True, "lambda_source": lambda_source,
        "issuance_dates": [t.isoformat() for t in issued_at_list], "issuances": issuances,
        "removed_by_min_possessions": removed, "sources": sources,
        "players_at_final_issuance": len(rows[-1]) if rows else 0, "code_sha256": code_sha,
        "files": {"rapm_pregame.parquet": _sha(tmp / "rapm_pregame.parquet")},
    }
    write_json_atomic(manifest, tmp / "manifest.json", indent=2)
    try:
        os.rename(tmp, run_dir)
    except OSError:
        if not (run_dir / "manifest.json").exists():
            raise
        shutil.rmtree(tmp)
    print(f"Wrote RAPM pregame {run_id}: target={target} lambda={lam} issuances={len(issued_at_list)} "
         f"-> {run_dir}")
    return run_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target-season", required=True)
    ap.add_argument("--run", action="append", required=True, metavar="SEASON=RUN_DIR",
                    help="exact releasable challenger run per pooled season (target and up to two prior)")
    ap.add_argument("--lambda-from", type=Path, required=True,
                    help="v2 fit dir for season S-1 (the frozen, past-only lambda source)")
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--cadence-days", type=int, default=7)
    ap.add_argument("--decay", type=float, default=0.80)
    ap.add_argument("--min-poss", type=int, default=3)
    args = ap.parse_args()
    runs = dict(r.split("=", 1) for r in args.run)
    build(args.target_season, runs, args.lambda_from, args.out_root.resolve(), args.data_root.resolve(),
         cadence_days=args.cadence_days, decay=args.decay, min_poss=args.min_poss)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
