"""Regenerate every number in the PMI abstract from the per-game tables in data/.

Needs only numpy and pandas. Inputs:
  data/pmi_games_track_a.csv, data/pmi_games_track_b.csv  per-game evaluation tables
  data/frozen_parameters.json   development-only offsets h and residual quantiles (frozen
                                before the holdout was read)
  data/expected.json            the committed report's values, for checking

A forecast is PLAYER_PART_<model> + h[model]. Track B (projected participation) is the
operational pregame track; Track A uses observed participation and is a diagnostic.
Exit status is 1 if anything fails to match expected.json.

    python reproduce.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MODELS = ("pregame_v1", "B0_home_only", "B1_prev_v2", "B2_prev_incumbent")
LABEL = {"pregame_v1": "Weekly past-only reconciled", "B0_home_only": "Home court only",
         "B1_prev_v2": "Prior-season reconciled", "B2_prev_incumbent": "Prior-season legacy"}
frozen = json.loads((DATA / "frozen_parameters.json").read_text(encoding="utf-8"))
expected = json.loads((DATA / "expected.json").read_text(encoding="utf-8"))
failures = []


def check(name, got, want, tol):
    ok = abs(got - want) <= tol
    if not ok:
        failures.append(f"{name}: got {got:.6f}, expected {want:.6f}")
    return ok


def rmse(a, p):
    return float(np.sqrt(np.mean((a - p) ** 2)))


def paired_bootstrap(actual, pa, pb, n=2000, seed=20260926):
    """Paired game-level bootstrap of RMSE(a) - RMSE(b); identical to the evaluation code."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, len(actual), size=len(actual))
        diffs[i] = rmse(actual[idx], pa[idx]) - rmse(actual[idx], pb[idx])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


results = {}
for track in ("track_a", "track_b"):
    df = pd.read_csv(DATA / f"pmi_games_{track}.csv", dtype={"GAME_ID": str}).sort_values("EVAL_ORDER")
    fz = frozen[track]
    out = results[track] = {}
    for phase in ("development", "holdout"):
        m = df[(df["PHASE"] == phase) & (df["MATCHED"])]
        y = m["ACTUAL"].to_numpy()
        for model in MODELS:
            pred = (m[f"PLAYER_PART_{model}"] + fz[model]["h"]).to_numpy()
            r = rmse(y, pred)
            check(f"{track} {phase} pooled {model} RMSE", r, expected[track][phase]["pooled"][model]["rmse"], 5e-7)
            out[(phase, model, "rmse")] = r
            if phase == "holdout":
                cov = float(np.mean((y >= pred + fz[model]["q10"]) & (y <= pred + fz[model]["q90"])))
                out[(phase, model, "coverage")] = cov
                check(f"{track} holdout {model} coverage", cov, expected[track]["holdout"]["pooled"][model]["interval_coverage"], 5e-7)
            for season in sorted(m["SEASON"].unique()):
                s = m["SEASON"] == season
                check(f"{track} {phase} {season} {model} RMSE", rmse(y[s.to_numpy()], pred[s.to_numpy()]),
                      expected[track][phase][season][model]["rmse"], 5e-7)
        if phase == "holdout":
            cand = (m["PLAYER_PART_pregame_v1"] + fz["pregame_v1"]["h"]).to_numpy()
            for base in ("B0_home_only", "B1_prev_v2", "B2_prev_incumbent"):
                bp = (m[f"PLAYER_PART_{base}"] + fz[base]["h"]).to_numpy()
                lo, hi = paired_bootstrap(y, cand, bp)
                want = expected["promotion_bootstrap"][track][base]
                check(f"{track} weekly-vs-{base} CI low", lo, want["ci_low"], 1e-6)
                check(f"{track} weekly-vs-{base} CI high", hi, want["ci_high"], 1e-6)
                out[("ci_weekly_vs", base)] = (lo, hi)

    # post hoc: development-only linear rescaling of every rating-based forecast
    d = df[(df["PHASE"] == "development") & (df["MATCHED"])]
    h = df[(df["PHASE"] == "holdout") & (df["MATCHED"])]
    y = h["ACTUAL"].to_numpy()
    rec = {}
    for model in ("pregame_v1", "B1_prev_v2", "B2_prev_incumbent"):
        slope, icpt = np.polyfit(d[f"PLAYER_PART_{model}"].to_numpy(), d["ACTUAL"].to_numpy(), 1)
        rec[model] = icpt + slope * h[f"PLAYER_PART_{model}"].to_numpy()
        out[("dev_slope", model)] = float(slope)
        out[("rescaled_rmse", model)] = rmse(y, rec[model])
        check(f"{track} dev slope {model}", slope, expected["recalibration"][track][model]["dev_slope"], 5e-4)
        check(f"{track} rescaled RMSE {model}", rmse(y, rec[model]), expected["recalibration"][track][model]["rescaled_rmse"], 5e-4)
    for a, b in (("B1_prev_v2", "B2_prev_incumbent"), ("pregame_v1", "B1_prev_v2")):
        lo, hi = paired_bootstrap(y, rec[a], rec[b])
        pt = rmse(y, rec[a]) - rmse(y, rec[b])
        out[("rescaled_diff", a, b)] = (pt, lo, hi)
        want = expected["recalibration"][track][f"{a}-{b}"]
        check(f"{track} rescaled {a}-{b} point", pt, want["point"], 5e-4)
        check(f"{track} rescaled {a}-{b} CI low", lo, want["ci_low"], 5e-4)
        check(f"{track} rescaled {a}-{b} CI high", hi, want["ci_high"], 5e-4)
        for season in sorted(h["SEASON"].unique()):
            s = (h["SEASON"] == season).to_numpy()
            out[("rescaled_diff_season", a, b, season)] = rmse(y[s], rec[a][s]) - rmse(y[s], rec[b][s])

tb = results["track_b"]
print("Table 1 - holdout RMSE, home margin per 100 combined possessions (2,430 games, Track B)")
print(f"{'Forecast':36s} {'As frozen':>9s} {'Rescaled (post hoc)':>20s}")
for model in ("B0_home_only", "B2_prev_incumbent", "B1_prev_v2", "pregame_v1"):
    resc = tb.get(("rescaled_rmse", model))
    print(f"{LABEL[model]:36s} {tb[('holdout', model, 'rmse')]:9.3f} {('%.3f' % resc) if resc else '-':>20s}")
lo, hi = tb[("ci_weekly_vs", "B1_prev_v2")]
print(f"\nWeekly vs prior-season reconciled, as frozen: 95% paired interval [{lo:.3f}, {hi:.3f}]")
print(f"Legacy development calibration slope: {tb[('dev_slope', 'B2_prev_incumbent')]:.3f}")
for (a, b) in (("B1_prev_v2", "B2_prev_incumbent"), ("pregame_v1", "B1_prev_v2")):
    pt, lo, hi = tb[("rescaled_diff", a, b)]
    seasons = ", ".join(f"{s} {tb[('rescaled_diff_season', a, b, s)]:+.3f}" for s in ("2023-24", "2024-25"))
    print(f"Rescaled {LABEL[a]} - {LABEL[b]}: {pt:+.3f} [{lo:+.3f}, {hi:+.3f}]  ({seasons})")
print(f"Weekly model 80% interval coverage: {tb[('holdout', 'pregame_v1', 'coverage')]:.3f}")

print()
if failures:
    print(f"FAILED: {len(failures)} value(s) differ from expected.json")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("OK: every value matches the committed results")
