"""Rebuild data/pmi_games_track_{a,b}.csv from an externally supplied source checkout.

This is the "where did the numbers come from" path. It runs the evaluation code in pipeline/ (the
code exactly as of the evaluation commit e3140577b) over the raw and derived inputs in source_data/:
the season release runs (reconciled possessions and stints), the v2 and weekly pregame rating fits,
the NBA.com fact tables and the play-by-play whose sha256 hashes the season manifests seal. It then
requires the rebuilt per-game tables to equal the published ones. Exit status 1 on any difference.

The upstream source is NOT bundled in this package and is NOT a git submodule: this candidate
contains no .gitmodules and no gitlink, so `git submodule update --init` does nothing here. Supply
the source checkout yourself at source_data/ (see source_data/README.md). That is an external,
privately held input, so this path is not part of the public reproduction level.

    # with an external source checkout placed at source_data/:
    python rebuild_tables.py

Extra dependencies beyond requirements.txt: see requirements-rebuild.txt.
"""
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "source_data"
DATA_ROOT = SRC / "data_root"
sys.path.insert(0, str(ROOT / "pipeline"))
sys.stdout.reconfigure(encoding="utf-8")

if not (SRC / "MANIFEST.sha256").exists():
    sys.exit(
        "source_data/ is empty. The upstream source is not bundled in this package and is NOT a "
        "git submodule, so `git submodule update --init` will not fetch it. Place an external "
        "source checkout at source_data/ (see source_data/README.md)."
    )

import scripts.nba_value.analysis.evaluate_player_impact as E  # noqa: E402
import scripts.nba_value.calibration.fit_rapm_corrected as F  # noqa: E402

frozen = json.loads((ROOT / "data/frozen_parameters.json").read_text(encoding="utf-8"))
SEASONS = ["2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]


def one(pattern):
    hits = glob.glob(str(pattern))
    if len(hits) != 1:
        sys.exit(f"expected exactly one match for {pattern}, found {hits}")
    return Path(hits[0])


def by_season(root, key):
    out = {}
    for m in glob.glob(str(SRC / root / "*" / "manifest.json")):
        d = json.loads(Path(m).read_text(encoding="utf-8"))
        season = d.get(key) or d.get("target_season") or d.get("season")
        if season in out:
            sys.exit(f"duplicate {root} run for {season}")
        out[season] = Path(m).parent
    return out


def local_copy(recorded):
    """Map a path recorded in a manifest to the same file inside source_data/ (the manifests record
    the authors' checkout; only the trailing, checkout-relative part is meaningful)."""
    p = recorded.replace("\\", "/")
    for marker, base in (("api/src/airflow_project/data/", DATA_ROOT), ("data/bronze/", SRC / "bronze")):
        if marker in p:
            return base / p.split(marker, 1)[1]
    return Path(recorded)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_releasable(run_dir):
    """Same predicate as the original load_releasable_run, but every sealed input is located inside
    source_data/ and checked by sha256. A missing or different file refuses."""
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    def entries(d):
        for k, v in d.items():
            if isinstance(v, dict) and "sha256" in v:
                yield k, v
            elif isinstance(v, dict):
                yield from entries(v)

    bad = [k for k, v in entries(manifest["inputs"]) if not (local_copy(v["path"]).exists() and sha(local_copy(v["path"])) == v["sha256"])]
    if manifest["release"]["status"] not in F.RELEASABLE or bad:
        sys.exit(f"REFUSED {run_dir.name}: status={manifest['release']['status']}, unverifiable sealed inputs {bad[:5]} (+{max(0, len(bad) - 5)})")
    return pd.read_parquet(run_dir / "stints.parquet"), manifest


E.load_releasable_run = verified_releasable

season_runs = {s: one(SRC / "runs/season_release" / s / "*") for s in SEASONS}
pregame_runs = by_season("runs/rapm_pregame", "target_season")
v2_fits = by_season("runs/rapm_v2", "season")

psf = pd.read_parquet(DATA_ROOT / "gold/features/player_season_features.parquet", columns=["PLAYER_ID", "SEASON_ID", "RAPM_NET"])
pgf = pd.read_parquet(DATA_ROOT / "silver/nba/facts/player_game_fact.parquet", columns=["PLAYER_ID", "TEAM_ID", "GAME_ID", "GAME_DATE", "MIN"])
pgf = pgf.assign(GAME_ID=E._zfill(pgf["GAME_ID"]))
pgf_reg = pgf[pgf["GAME_ID"].str.startswith(E.REGULAR_SEASON_PREFIX)].copy()
tg = pd.read_parquet(DATA_ROOT / "silver/nba/facts/team_game_fact.parquet", columns=["GAME_ID", "TEAM_ID", "GAME_DATE", "SEASON_ID"])
tg = tg.assign(GAME_ID=E._zfill(tg["GAME_ID"]))
tg_reg = tg[tg["GAME_ID"].str.startswith(E.REGULAR_SEASON_PREFIX)].copy()
team_sched = E.build_team_schedule(tg_reg)
pgf_by = E.build_team_game_players(pgf_reg)
hist = pgf_reg[["PLAYER_ID", "GAME_DATE", "TEAM_ID"]].sort_values("GAME_DATE").reset_index(drop=True)


def frames(seasons):
    fa, fb = [], []
    for season in seasons:
        prior = E.prior_season(season)
        stints, poss, _m, _g = E.load_season_run(season_runs[season], tg_reg)
        pst, _, _, _ = E.load_season_run(season_runs[prior], tg_reg)
        vets = {int(p) for lu in pd.concat([pst["home_lineup"], pst["away_lineup"]], ignore_index=True) for p in lu}
        v2 = E.load_v2_theta(v2_fits[prior], prior)
        gold = E.load_gold_theta(psf, prior)
        pre = E.load_pregame_run(pregame_runs[season], season)
        fa.append(E.build_track_a(season, stints, poss, pre, v2, gold, vets, hist))
        fb.append(E.build_track_b(season, poss, pre, v2, gold, vets, team_sched, pgf_by, hist))
    fa = E.attach_rookie_heavy(E.attach_early_season(pd.concat(fa)))[0]
    fb = E.attach_rookie_heavy(E.attach_early_season(pd.concat(fb)))[0]
    return {"track_a": fa, "track_b": fb}


dev = frames(E.DEVELOPMENT_SEASONS)
hold = frames(E.HOLDOUT_SEASONS)

KEEP = ["GAME_ID", "SEASON", "GAME_DATE", "PHASE", "ACTUAL", "WEIGHT", "MATCHED", "EARLY_SEASON",
        "ROOKIE_HEAVY", "TEAM_CHANGE", "ROOKIE_SHARE"]
failures = []
for tname in ("track_a", "track_b"):
    parts = []
    for phase, fr in (("development", dev), ("holdout", hold)):
        f = fr[tname].copy()
        f["PHASE"] = phase
        f = f.reset_index().rename(columns={f.index.name or "index": "GAME_ID"})
        parts.append(f)
    out = pd.concat(parts, ignore_index=True)
    cols = KEEP + [c for c in out.columns if c.startswith("PLAYER_PART_") or c.startswith("RATED_SHARE_")]
    out = out[cols].reset_index(drop=True)
    out.insert(0, "EVAL_ORDER", range(len(out)))
    out["GAME_DATE"] = pd.to_datetime(out["GAME_DATE"]).dt.strftime("%Y-%m-%d")
    published = pd.read_csv(ROOT / f"data/pmi_games_{tname}.csv", dtype={"GAME_ID": str})
    rebuilt = pd.read_csv(pd.io.common.StringIO(out.to_csv(index=False, float_format="%.10g")), dtype={"GAME_ID": str})
    if list(rebuilt.columns) != list(published.columns) or len(rebuilt) != len(published):
        failures.append(f"{tname}: shape/columns differ ({rebuilt.shape} vs {published.shape})")
        continue
    num = [c for c in published.columns if pd.api.types.is_numeric_dtype(published[c]) and c != "EVAL_ORDER"]
    for c in published.columns:
        if c in num:
            same = np.allclose(rebuilt[c].to_numpy(float), published[c].to_numpy(float), rtol=1e-9, atol=1e-9, equal_nan=True)
        else:
            same = (rebuilt[c].astype(str).to_numpy() == published[c].astype(str).to_numpy()).all()
        if not same:
            failures.append(f"{tname}.{c}")
    print(f"{tname}: {len(rebuilt)} games rebuilt from source_data/; columns compared: {len(published.columns)}")

if failures:
    print("FAILED: rebuilt tables differ from data/*.csv:", ", ".join(failures[:10]))
    sys.exit(1)
print("OK: source_data/ regenerates the published per-game tables (every column, to 1e-9)")
