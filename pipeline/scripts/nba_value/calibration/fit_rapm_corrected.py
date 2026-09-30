"""Corrected RAPM v2 (candidate) on the D1b possession challenger's stints.

Estimator `betts.rapm.corrected_possessions.v2`: ridge RAPM over the challenger's
stints (real possessions in the real home frame, raw targets -- not luck
adjusted), pooled over `--seasons-back` seasons with per-season decay. It never
redefines the incumbent RAPM_NET and writes only a candidate run.

Guards:
  * every pooled season's challenger run must be releasable -- its release status
    PASS / PASS_WITH_EXCLUSIONS AND the independent SQL gate fully green -- or the
    fit refuses to run (no model on unreleased possessions);
  * the minimum-possessions-per-stint filter is applied here, in the fitting layer,
    and the stints/points/possessions it removes are counted in the manifest;
  * lambda is tuned chronologically by forward chaining: the target season's last
    `--holdout-fraction` of games (by date) is split into `--n-folds` consecutive
    blocks, each scored (possession-weighted error of its stints' net rating) by a
    fit on strictly earlier stints only. A paired one-standard-error rule picks the
    largest lambda whose per-fold error excess over the best lambda is within one
    standard error of that excess, so a flat curve resolves toward shrinkage while
    block-to-block noise shared by every lambda does not; grid-edge choices are
    flagged. The final fit uses all stints with that lambda, frozen in the manifest.

  <out-root>/<RUN_ID>/rapm_v2.parquet, manifest.json

Usage:
  python scripts/nba_value/calibration/fit_rapm_corrected.py --target-season 2024-25 \\
      --run 2022-23=<release run dir> --run 2023-24=<dir> --run 2024-25=<dir> --out-root <scratch>
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api.src.ml.features.rapm_pipeline.design_matrix import build_multi_season_matrix
from api.src.ml.io.atomic_io import write_json_atomic, write_parquet_atomic
from scripts.nba_value.validation.validate_possession_challenger import run_checks

ESTIMATOR_ID = "betts.rapm.corrected_possessions.v2"
DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"
RELEASABLE = ("PASS", "PASS_WITH_EXCLUSIONS")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_releasable_run(run_dir: Path) -> tuple[pd.DataFrame, dict]:
    """The run's stints, only if the run is releasable (predicate AND gate)."""
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    failed = [name for name, ok, _ in run_checks(run_dir) if not ok]
    if manifest["release"]["status"] not in RELEASABLE or failed:
        raise ValueError(f"{run_dir.name} ({manifest['season']}) is not releasable: "
                         f"release={manifest['release']['status']} gate_failures={failed}")
    stints = pd.read_parquet(run_dir / "stints.parquet")
    return stints, manifest


def filter_min_possessions(stints: pd.DataFrame, min_poss: int) -> tuple[pd.DataFrame, dict]:
    keep = stints["possessions"] >= min_poss
    removed = stints[~keep]
    return stints[keep].reset_index(drop=True), {
        "stints": int((~keep).sum()), "possessions": float(removed["possessions"].sum()),
        "home_points": float(removed["home_points"].sum()),
        "away_points": float(removed["away_points"].sum())}


def _fit(season_stints: dict, target: str, decay: float, lam: float, row_mask=None):
    X, y, w, index = build_multi_season_matrix(season_stints, target, decay)
    if row_mask is not None:
        X, y, w = X[row_mask], y[row_mask], w[row_mask]
    model = Ridge(alpha=lam, fit_intercept=True)
    model.fit(X, y, sample_weight=w)
    return model, index


def forward_chaining_folds(row_rank: np.ndarray, n_games: int, n_hold: int,
                           n_folds: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """(train, score) row masks. `row_rank`: each stint's game's chronological rank in
    the target season, NaN for prior-season stints. The last `n_hold` games form
    `n_folds` consecutive blocks; a block is scored by a fit on prior seasons and the
    target season's games strictly before the block -- never a later game."""
    ranks = np.arange(n_games - n_hold, n_games)
    folds = []
    for block in np.array_split(ranks, n_folds):
        prior = np.isnan(row_rank)
        train = prior | (row_rank < block[0])
        score = np.isin(row_rank, block)
        folds.append((train, score))
    return folds


def select_lambda(fold_mse: dict) -> dict:
    """Paired one-standard-error rule: the largest lambda (most shrinkage) whose mean
    per-fold error excess over the lowest-mean lambda is within one standard error
    of that excess. The folds are shared, so lambdas are compared on paired
    differences: an unpaired rule lets the block-to-block error level (every lambda
    moves with it) swamp the lambda effect and returns the grid's largest value
    (2015-16..2024-25 corrected stints: fold SE 10-43 against a 7-29 curve range)."""
    folds = {lam: np.asarray(v, dtype=float) for lam, v in fold_mse.items()}
    mean = {lam: float(v.mean()) for lam, v in folds.items()}
    lam_min = min(mean, key=mean.get)
    excess = {lam: folds[lam] - folds[lam_min] for lam in folds}
    excess_mean = {lam: float(d.mean()) for lam, d in excess.items()}
    excess_se = {lam: float(d.std(ddof=1) / np.sqrt(len(d))) for lam, d in excess.items()}
    lam_1se = max(lam for lam in folds if excess_mean[lam] <= excess_se[lam])
    grid = sorted(mean)
    return {"rule": "paired_one_standard_error_largest_lambda", "lambda_min": lam_min, "lambda_1se": lam_1se,
            "mean_mse_by_lambda": mean, "excess_mean_by_lambda": excess_mean,
            "excess_se_by_lambda": excess_se,
            "lambda_min_at_grid_edge": lam_min in (grid[0], grid[-1]),
            "lambda_at_grid_edge": lam_1se in (grid[0], grid[-1])}


def tune_lambda(season_stints: dict, target: str, decay: float, lambdas: list,
                game_dates: pd.Series, holdout_fraction: float, n_folds: int) -> tuple[float, dict]:
    """Forward-chaining validation inside the target season (see the module doc)."""
    if n_folds < 2:
        raise ValueError("n_folds must be >= 2: the selection rule needs a standard error across folds")
    combined = pd.concat([season_stints[s] for s in sorted(season_stints)], ignore_index=True)
    target_rows = (combined["season"] == target).to_numpy()
    games = combined.loc[target_rows, "game_id"].drop_duplicates()
    dates = games.map(game_dates)
    if dates.isna().any():
        raise ValueError("target-season games without a date; cannot order the validation folds")
    ordered = games.to_numpy()[np.argsort(dates.to_numpy(), kind="mergesort")]
    n_hold = int(np.ceil(len(ordered) * holdout_fraction))
    if n_hold < n_folds:
        raise ValueError(f"{n_hold} held-out games cannot form {n_folds} folds")
    rank = pd.Series(np.arange(len(ordered), dtype=float), index=ordered)
    row_rank = combined["game_id"].map(rank).where(target_rows).to_numpy(dtype=float)
    X, y, w, _ = build_multi_season_matrix(season_stints, target, decay)
    folds = forward_chaining_folds(row_rank, len(ordered), n_hold, n_folds)
    fold_mse = {float(lam): [] for lam in lambdas}
    for train, score in folds:
        for lam in lambdas:
            model = Ridge(alpha=lam, fit_intercept=True).fit(X[train], y[train], sample_weight=w[train])
            err = model.predict(X[score]) - y[score]
            fold_mse[float(lam)].append(float(np.average(err ** 2, weights=w[score])))
    sel = select_lambda(fold_mse)
    return sel["lambda_1se"], {"validation": "forward_chaining", "n_folds": n_folds, "holdout_games": n_hold,
                               "fold_games": [combined.loc[s, "game_id"].nunique() for _, s in folds],
                               "fold_mse_by_lambda": fold_mse, **sel}


def coefficients(season_stints: dict, target: str, decay: float, lam: float) -> tuple[pd.DataFrame, float]:
    model, index = _fit(season_stints, target, decay, lam)
    tgt = season_stints[target]
    lineups = tgt["home_lineup"].map(list) + tgt["away_lineup"].map(list)
    on = (pd.DataFrame({"PLAYER_ID": lineups, "POSS": tgt["possessions"].astype(float)})
          .explode("PLAYER_ID").astype({"PLAYER_ID": "int64"}).groupby("PLAYER_ID")
          .agg(TARGET_POSSESSIONS=("POSS", "sum"), N_STINTS=("POSS", "size")))
    out = pd.DataFrame({"PLAYER_ID": list(index), "RAPM_NET": model.coef_[list(index.values())]})
    out = out.merge(on, on="PLAYER_ID", how="inner")          # players seen in the target season
    out.insert(1, "SEASON", target)
    out["ESTIMATOR_ID"] = ESTIMATOR_ID
    return out.sort_values("PLAYER_ID").reset_index(drop=True), float(model.intercept_)


def build(target: str, runs: dict, out_root: Path, data_root: Path = DATA_ROOT, *, decay: float,
          min_poss: int, lambdas: list, holdout_fraction: float, n_folds: int) -> Path:
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
    if target not in season_stints:
        raise ValueError(f"target season {target} has no run")
    tg = pd.read_parquet(data_root / "silver/nba/facts/team_game_fact.parquet", columns=["GAME_ID", "GAME_DATE"])
    dates = tg.assign(GAME_ID=tg["GAME_ID"].astype(str).str.zfill(10)).drop_duplicates("GAME_ID") \
        .set_index("GAME_ID")["GAME_DATE"]
    lam, tuning = tune_lambda(season_stints, target, decay, lambdas, dates, holdout_fraction, n_folds)
    coefs, intercept = coefficients(season_stints, target, decay, lam)

    code_sha = _sha(Path(__file__).resolve())
    ident = json.dumps({"sources": {s: v["manifest_sha256"] for s, v in sources.items()},
                        "target": target, "decay": decay, "min_poss": min_poss, "lambdas": lambdas,
                        "holdout_fraction": holdout_fraction, "n_folds": n_folds, "code": code_sha},
                       sort_keys=True)
    run_id = hashlib.sha256(ident.encode()).hexdigest()[:16]
    run_dir = out_root / run_id
    if (run_dir / "manifest.json").exists():
        print(f"RAPM v2 run {run_id} already exists -- not rewritten.")
        return run_dir
    tmp = out_root / f".{run_id}.partial-{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=False)
    write_parquet_atomic(coefs, tmp / "rapm_v2.parquet", index=False)
    manifest = {
        "product": "rapm_corrected_candidate", "estimator_id": ESTIMATOR_ID, "run_id": run_id,
        "target_season": target, "created_at_utc": datetime.now(UTC).isoformat(),
        "rate_unit": "net points per 100 combined (both-team) possessions, challenger possessions",
        "construction": "raw targets (not luck adjusted); ridge with intercept; real home frame",
        "pooled_seasons": sorted(season_stints), "decay": decay, "min_poss_per_stint": min_poss,
        "lambda": lam, "lambda_frozen": True, "tuning": {"holdout_fraction": holdout_fraction, **tuning},
        "intercept": intercept, "removed_by_min_possessions": removed, "sources": sources,
        "players": len(coefs), "code_sha256": code_sha,
        "files": {"rapm_v2.parquet": _sha(tmp / "rapm_v2.parquet")},
    }
    write_json_atomic(manifest, tmp / "manifest.json", indent=2)
    try:
        os.rename(tmp, run_dir)
    except OSError:
        if not (run_dir / "manifest.json").exists():
            raise
        shutil.rmtree(tmp)
    print(f"Wrote RAPM v2 candidate {run_id}: target={target} lambda={lam} players={len(coefs)} -> {run_dir}")
    return run_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target-season", required=True)
    ap.add_argument("--run", action="append", required=True, metavar="SEASON=RUN_DIR",
                    help="exact releasable challenger run per pooled season")
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--decay", type=float, default=0.80)
    ap.add_argument("--min-poss", type=int, default=3)
    ap.add_argument("--lambdas", type=float, nargs="+",
                    default=[250, 500, 1000, 2000, 3500, 5000, 8000, 12000, 16000, 24000, 32000])
    ap.add_argument("--holdout-fraction", type=float, default=0.4)
    ap.add_argument("--n-folds", type=int, default=4)
    args = ap.parse_args()
    runs = dict(r.split("=", 1) for r in args.run)
    build(args.target_season, runs, args.out_root.resolve(), args.data_root.resolve(), decay=args.decay,
          min_poss=args.min_poss, lambdas=args.lambdas, holdout_fraction=args.holdout_fraction,
          n_folds=args.n_folds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
