"""Render the executed saved-forecast diagnostics; requires matplotlib.

python make_figures.py --results supplement/supplement_results.json --output supplement/figures
"""
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--results", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(args.output / "matplotlib_cache")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

report = json.loads(args.results.read_text(encoding="utf-8"))
track = report["tracks"]["track_b"]
original = track["variants"]["as_frozen"]
rescaled = track["variants"]["development_rescaled_post_hoc"]
names = ["B0_home_only", "B2_prev_incumbent", "B1_prev_v2", "pregame_v1"]
labels = ["Home court", "Prior legacy", "Prior reconciled", "Weekly reconciled"]
blue, orange = "#245A81", "#BB6528"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "none", "savefig.facecolor": "white"})

fig, axes = plt.subplots(1, 2, figsize=(12, 5.1), gridspec_kw={"width_ratios": [1.12, 1]})
for i, model in enumerate(names):
    a, b = original["metrics"][model]["rmse"], rescaled["metrics"][model]["rmse"]
    axes[0].plot([a, b], [i, i], color="#B9C5CC", linewidth=3)
    axes[0].scatter(a, i - .075, color=blue, s=70, label="Frozen" if i == 0 else None)
    axes[0].scatter(b, i + .075, color=orange, s=65, marker="D", label="Development-rescaled (post hoc)" if i == 0 else None)
    axes[0].annotate(f"{a:.3f}", (a, i - .075), xytext=(6, -5), textcoords="offset points", color=blue, fontsize=9)
    if abs(a - b) > .01:
        axes[0].annotate(f"{b:.3f}", (b, i + .075), xytext=(-4, 9), textcoords="offset points", color=orange, fontsize=9, ha="right")
axes[0].set_yticks(range(4), labels)
axes[0].invert_yaxis()
axes[0].set_xlim(6.95, 8.13)
axes[0].set_xlabel("RMSE: home margin per 100 combined possessions")
axes[0].set_title("A. Fair calibration changes the model ladder", loc="left", fontsize=12)
axes[0].grid(axis="x", alpha=.2)
axes[0].legend(loc="lower left", bbox_to_anchor=(0, -0.40), frameon=False, fontsize=9)
for offset, variant, color, label in [(-.09, original, blue, "Frozen"), (.09, rescaled, orange, "Rescaled")]:
    block = variant["calendar_cluster_sensitivity"]["28"]["contrasts"]
    for i, key in enumerate(["B1_prev_v2-B2_prev_incumbent", "pregame_v1-B1_prev_v2"]):
        item = block[key]
        point = -item["rmse_difference"]
        lo, hi = [-value for value in item["rmse_percentile_95"][::-1]]
        axes[1].errorbar(point, i + offset, xerr=np.array([[point - lo], [hi - point]]),
                         fmt="o" if color == blue else "D", color=color, capsize=4, markersize=7)
axes[1].set_yticks([0, 1], ["Accounting +\nregularisation", "Weekly updating"])
axes[1].invert_yaxis()
axes[1].set_xlim(0, .57)
axes[1].set_xlabel("RMSE improvement over preceding comparator")
axes[1].set_title("B. Relative gains reverse after calibration", loc="left", fontsize=12)
axes[1].grid(axis="x", alpha=.2)
fig.suptitle("PMI operational Track B | 2,430 matched evaluation games", x=.06, ha="left", fontsize=15, fontweight="bold")
fig.text(.06, .02, "Panel B: post hoc 28-day calendar-cluster intervals; fixed predictions, not causal effects or fresh validation.", fontsize=9, color="#45515B")
fig.subplots_adjust(left=.15, right=.97, top=.83, bottom=.29, wspace=.72)
for suffix in ("png", "svg"):
    fig.savefig(args.output / f"fig1_calibration_and_gains.{suffix}", dpi=180)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9))
for i, model in enumerate(names):
    metric = original["metrics"][model]
    color = blue if model == "pregame_v1" else "#667985"
    axes[0].scatter(metric["mean_interval_width"], metric["coverage_80"] * 100, color=color, s=80)
    axes[0].annotate(labels[i], (metric["mean_interval_width"], metric["coverage_80"] * 100),
                     xytext=(5, 5), textcoords="offset points", fontsize=9)
    axes[1].scatter(metric["interval_score_80"], i, color=color, s=65)
    axes[1].annotate(f"{metric['interval_score_80']:.2f}", (metric["interval_score_80"], i), xytext=(6, -4), textcoords="offset points", fontsize=9)
axes[0].axhline(80, linestyle="--", color=orange, linewidth=1.2, label="Nominal 80%")
axes[0].set_xlim(16.35, 19.2)
axes[0].set_ylim(75, 81)
axes[0].set_xlabel("Mean interval width (normalized margin units)")
axes[0].set_ylabel("Evaluation coverage (%)")
axes[0].legend(frameon=False, fontsize=9)
axes[0].set_title("A. All frozen intervals undercover", loc="left", fontsize=12)
axes[1].set_yticks(range(4), labels)
axes[1].invert_yaxis()
axes[1].set_xlim(25, 29)
axes[1].set_xlabel("Mean central-80% interval score (lower is better)")
axes[1].set_title("B. Width and misses jointly penalized", loc="left", fontsize=12)
axes[1].grid(axis="x", alpha=.2)
fig.suptitle("Point accuracy does not establish calibrated uncertainty", x=.07, ha="left", fontsize=15, fontweight="bold")
fig.text(.07, .02, "Saved-forecast, post hoc diagnostics. Score differences are descriptive; no score-difference significance test.", fontsize=9, color="#45515B")
fig.subplots_adjust(left=.08, right=.96, top=.80, bottom=.22, wspace=.75)
for suffix in ("png", "svg"):
    fig.savefig(args.output / f"fig2_interval_quality.{suffix}", dpi=180)
plt.close(fig)
print("OK: two figures rendered as PNG and SVG")
