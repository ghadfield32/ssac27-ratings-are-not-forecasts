"""Post hoc, fixed-prediction PMI diagnostics. Never trains or changes inputs.

python supplement_analysis.py --package PATH --output PATH
Calendar intervals are sensitivity analyses, not fresh validation or uncertainty
over model fitting. The original frozen game-bootstrap results are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

MODELS = ("B0_home_only", "B2_prev_incumbent", "B1_prev_v2", "pregame_v1")
BLOCK_DAYS = (7, 14, 28)


def load_track(package: Path, track: str) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(package / "data" / f"pmi_games_{track}.csv", dtype={"GAME_ID": str})
    frozen = json.loads((package / "data/frozen_parameters.json").read_text(encoding="utf-8"))[track]
    required = {"GAME_ID", "EVAL_ORDER", "GAME_DATE", "SEASON", "PHASE", "MATCHED", "ACTUAL",
                "EARLY_SEASON", "ROOKIE_HEAVY", "TEAM_CHANGE"} | {f"PLAYER_PART_{m}" for m in MODELS}
    if not required.issubset(frame.columns):
        raise ValueError(f"missing columns: {sorted(required - set(frame.columns))}")
    if frame["GAME_ID"].isna().any() or not frame["GAME_ID"].is_unique or not frame["EVAL_ORDER"].is_unique:
        raise ValueError("game identities and evaluation order must be unique")
    if not frame["GAME_ID"].str.fullmatch(r"002\d{7}").all():
        raise ValueError("expected ten-digit regular-season game IDs")
    order = frame["EVAL_ORDER"].to_numpy(dtype=float)
    if not np.isfinite(order).all() or not np.equal(order, np.floor(order)).all():
        raise ValueError("evaluation order must be finite integers")
    if frame["SEASON"].isna().any() or not frame["SEASON"].str.fullmatch(r"\d{4}-\d{2}").all():
        raise ValueError("invalid season labels")
    for flag in ("MATCHED", "EARLY_SEASON", "ROOKIE_HEAVY", "TEAM_CHANGE"):
        if frame[flag].dtype != bool or frame[flag].isna().any():
            raise ValueError(f"{flag} must be explicit booleans")
    if set(frame["PHASE"]) != {"development", "holdout"}:
        raise ValueError("expected development and holdout phases only")
    frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], format="%Y-%m-%d", errors="raise")
    if frame["GAME_DATE"].isna().any():
        raise ValueError("dates cannot be missing")
    dev = frame[frame["PHASE"] == "development"]
    hold = frame[frame["PHASE"] == "holdout"]
    if dev["GAME_DATE"].max() >= hold["GAME_DATE"].min() or set(dev["SEASON"]) & set(hold["SEASON"]):
        raise ValueError("development must strictly precede holdout, with disjoint seasons")
    start_year = frame["SEASON"].str[:4].astype(int)
    end_suffix = frame["SEASON"].str[-2:].astype(int)
    if not (((start_year + 1) % 100) == end_suffix).all():
        raise ValueError("season years must be consecutive")
    allowed = {"development": {f"{year}-{(year + 1) % 100:02d}" for year in range(2016, 2023)},
               "holdout": {"2023-24", "2024-25"}}
    if any(not set(frame.loc[frame["PHASE"] == phase, "SEASON"]).issubset(seasons)
           for phase, seasons in allowed.items()):
        raise ValueError("season does not belong to the frozen phase")
    if not (frame["GAME_ID"].str[3:5].astype(int) == start_year % 100).all():
        raise ValueError("game identity disagrees with season")
    # Two calendar years allow the exceptional 2019-20 COVID schedule. Exact
    # date provenance is enforced by the CLI's immutable input binding below.
    if not ((frame["GAME_DATE"].dt.year == start_year) |
            (frame["GAME_DATE"].dt.year == start_year + 1)).all():
        raise ValueError("game date falls outside its season calendar years")
    matched = frame[frame["MATCHED"]]
    if any(not ((matched["PHASE"] == phase).any()) for phase in ("development", "holdout")):
        raise ValueError("both phases need matched games")
    columns = ["ACTUAL"] + [f"PLAYER_PART_{m}" for m in MODELS]
    if not np.isfinite(matched[columns].to_numpy(dtype=float)).all():
        raise ValueError("matched targets and forecasts must be finite; missing data is not dropped")
    for model in MODELS:
        params = frozen[model]
        if not np.isfinite([params["h"], params["q10"], params["q90"]]).all() or params["q10"] >= params["q90"]:
            raise ValueError(f"invalid frozen interval/offset for {model}")
        if params["n_development_games"] != int(dev["MATCHED"].sum()):
            raise ValueError("development count disagrees with frozen parameters")
    return frame.sort_values("EVAL_ORDER").reset_index(drop=True), frozen


def interval_metrics(actual: np.ndarray, pred: np.ndarray, q10: float, q90: float) -> dict:
    actual, pred = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    if actual.shape != pred.shape or actual.ndim != 1 or not len(actual):
        raise ValueError("expected aligned, nonempty vectors")
    if not np.isfinite(actual).all() or not np.isfinite(pred).all() or not np.isfinite([q10, q90]).all() or q10 >= q90:
        raise ValueError("invalid observations or interval")
    lower, upper = pred + q10, pred + q90
    score = upper - lower + 10 * np.maximum(lower - actual, 0) + 10 * np.maximum(actual - upper, 0)
    return {"coverage_80": float(np.mean((actual >= lower) & (actual <= upper))),
            "mean_interval_width": float(q90 - q10), "interval_score_80": float(score.mean()),
            "below_interval_fraction": float(np.mean(actual < lower)),
            "above_interval_fraction": float(np.mean(actual > upper))}


def fit_development_scale(player_part: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
    x, y = np.asarray(player_part, dtype=float), np.asarray(actual, dtype=float)
    if x.shape != y.shape or x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all() or not np.isfinite(y).all() or np.ptp(x) == 0:
        raise ValueError("development scale requires finite aligned, varying predictions")
    slope, intercept = np.polyfit(x, y, 1)
    return float(intercept), float(slope)


def calendar_mse_draws(squared_errors: np.ndarray, dates, seasons: np.ndarray, block_days: int,
                       n_resamples: int, seed: int) -> tuple[np.ndarray, dict]:
    sq = np.asarray(squared_errors, dtype=float)
    dates, seasons = pd.DatetimeIndex(dates), np.asarray(seasons)
    if sq.ndim != 2 or not len(sq) or len(dates) != len(sq) or len(seasons) != len(sq) or not np.isfinite(sq).all() or np.any(sq < 0):
        raise ValueError("calendar bootstrap needs finite aligned squared errors")
    if dates.isna().any() or pd.isna(seasons).any() or block_days not in BLOCK_DAYS or n_resamples < 2:
        raise ValueError("invalid dates, seasons, block length or resample count")
    rng = np.random.default_rng(seed)
    total = np.zeros((n_resamples, sq.shape[1]))
    counts_by_season = {}
    # Resample paired nonoverlapping calendar blocks within each season. Keep
    # original season game weights fixed; varying block sizes change only each
    # resampled season's mean. This targets the original season mixture.
    for season in sorted(set(seasons)):
        mask = seasons == season
        sd = dates[mask]
        anchor = sd.min().normalize() - pd.Timedelta(days=sd.min().weekday())
        keys = np.asarray((sd - anchor).days // block_days)
        unique = np.unique(keys)
        counts = np.array([(keys == key).sum() for key in unique], dtype=float)
        sums = np.array([sq[mask][keys == key].sum(axis=0) for key in unique])
        draws = rng.integers(0, len(unique), size=(n_resamples, len(unique)))
        season_mean = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)[:, None]
        total += season_mean * (int(mask.sum()) / len(sq))
        counts_by_season[str(season)] = len(unique)
    return total, counts_by_season


def point_metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    resid = actual - pred
    result = {"n": len(actual), "mse": float(np.mean(resid ** 2)),
              "rmse": float(np.sqrt(np.mean(resid ** 2))), "mae": float(np.mean(np.abs(resid))),
              "bias_actual_minus_prediction": float(resid.mean())}
    if np.ptp(pred) == 0:
        result.update(calibration_intercept=None, calibration_slope=None)
    else:
        slope, intercept = np.polyfit(pred, actual, 1)
        result.update(calibration_intercept=float(intercept), calibration_slope=float(slope))
    return result


def analyse_track(frame: pd.DataFrame, frozen: dict, n_resamples: int, seed: int) -> dict:
    dev = frame[(frame["PHASE"] == "development") & frame["MATCHED"]]
    hold = frame[(frame["PHASE"] == "holdout") & frame["MATCHED"]]
    y = hold["ACTUAL"].to_numpy(float)
    predictions = {"as_frozen": {}, "development_rescaled_post_hoc": {}}
    out = {"population": {"rows": len(frame), "matched_development": len(dev), "matched_holdout": len(hold),
                          "unmatched_by_season": frame[~frame["MATCHED"]].groupby("SEASON").size().astype(int).to_dict()},
           "development_scale": {}, "variants": {}, "subgroups_post_hoc": {}}
    for model in MODELS:
        predictions["as_frozen"][model] = hold[f"PLAYER_PART_{model}"].to_numpy(float) + frozen[model]["h"]
        if model == "B0_home_only":
            predictions["development_rescaled_post_hoc"][model] = predictions["as_frozen"][model].copy()
        else:
            intercept, slope = fit_development_scale(dev[f"PLAYER_PART_{model}"].to_numpy(float), dev["ACTUAL"].to_numpy(float))
            out["development_scale"][model] = {"intercept": intercept, "slope": slope}
            predictions["development_rescaled_post_hoc"][model] = intercept + slope * hold[f"PLAYER_PART_{model}"].to_numpy(float)
    for variant, by_model in predictions.items():
        result = out["variants"][variant] = {"metrics": {}, "calendar_cluster_sensitivity": {}}
        for model, pred in by_model.items():
            result["metrics"][model] = point_metrics(y, pred)
            if variant == "as_frozen":
                result["metrics"][model].update(interval_metrics(y, pred, frozen[model]["q10"], frozen[model]["q90"]))
        sq = np.column_stack([(y - by_model[m]) ** 2 for m in MODELS])
        point_mse = sq.mean(axis=0)
        for days in BLOCK_DAYS:
            draw, clusters = calendar_mse_draws(sq, hold["GAME_DATE"], hold["SEASON"].to_numpy(), days, n_resamples, seed)
            block = {"nonempty_clusters_by_season": clusters, "contrasts": {}}
            for a, b in (("pregame_v1", "B0_home_only"), ("pregame_v1", "B1_prev_v2"),
                         ("pregame_v1", "B2_prev_incumbent"), ("B1_prev_v2", "B2_prev_incumbent")):
                ai, bi = MODELS.index(a), MODELS.index(b)
                block["contrasts"][f"{a}-{b}"] = {
                    "mse_difference": float(point_mse[ai] - point_mse[bi]),
                    "mse_percentile_95": np.percentile(draw[:, ai] - draw[:, bi], [2.5, 97.5]).tolist(),
                    "rmse_difference": float(np.sqrt(point_mse[ai]) - np.sqrt(point_mse[bi])),
                    "rmse_percentile_95": np.percentile(np.sqrt(draw[:, ai]) - np.sqrt(draw[:, bi]), [2.5, 97.5]).tolist()}
            li, pi, wi = [MODELS.index(m) for m in ("B2_prev_incumbent", "B1_prev_v2", "pregame_v1")]
            direct = np.sqrt(draw[:, li]) - 2 * np.sqrt(draw[:, pi]) + np.sqrt(draw[:, wi])
            block["accounting_plus_regularisation_gain_minus_update_gain"] = {
                "rmse_difference": float(np.sqrt(point_mse[li]) - 2 * np.sqrt(point_mse[pi]) + np.sqrt(point_mse[wi])),
                "rmse_percentile_95": np.percentile(direct, [2.5, 97.5]).tolist(),
                "interpretation": "positive means the accounting-plus-regularisation contrast is larger; not a causal decomposition"}
            result["calendar_cluster_sensitivity"][str(days)] = block
        result["per_season"] = {}
        for season in sorted(hold["SEASON"].unique()):
            mask = (hold["SEASON"] == season).to_numpy()
            result["per_season"][season] = {m: point_metrics(y[mask], p[mask]) for m, p in by_model.items()}
    for flag in ("EARLY_SEASON", "ROOKIE_HEAVY", "TEAM_CHANGE"):
        mask = hold[flag].to_numpy()
        out["subgroups_post_hoc"][flag] = {"n": int(mask.sum()), "as_frozen": {
            m: point_metrics(y[mask], p[mask]) for m, p in predictions["as_frozen"].items()} if mask.any() else None}
    # Calibration bins are determined from development predictions, not evaluation labels.
    weekly_dev = dev["PLAYER_PART_pregame_v1"].to_numpy(float) + frozen["pregame_v1"]["h"]
    cutpoints = np.quantile(weekly_dev, [.2, .4, .6, .8])
    labels = np.searchsorted(cutpoints, predictions["as_frozen"]["pregame_v1"], side="right")
    out["weekly_calibration_bins_post_hoc"] = []
    for index in range(5):
        mask = labels == index
        out["weekly_calibration_bins_post_hoc"].append({"bin": index + 1, "n": int(mask.sum()),
            "mean_prediction": float(predictions["as_frozen"]["pregame_v1"][mask].mean()) if mask.any() else None,
            "mean_actual": float(y[mask].mean()) if mask.any() else None})
    out["development_bin_cutpoints"] = cutpoints.tolist()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261001)
    args = parser.parse_args()
    if args.resamples < 2 or args.seed < 0:
        parser.error("resamples >=2 and seed >=0 required")
    package, output = args.package.resolve(), args.output.resolve()
    if output == package or any(output == package / name or output.is_relative_to(package / name) for name in ("data", "pipeline", "source_data")):
        parser.error("output must not overwrite package inputs/code")
    input_paths = [package / "data" / f"pmi_games_{track}.csv" for track in ("track_a", "track_b")]
    input_paths += [package / "data/frozen_parameters.json", package / "data/expected.json"]
    hashes = {path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
    binding = json.loads(Path(__file__).with_name("input_bindings.json").read_text(encoding="utf-8"))
    if hashes != binding["input_sha256"]:
        raise RuntimeError("input binding mismatch: this supplement accepts only the reviewed frozen snapshot")
    results = {"analysis_status": "post_hoc_fixed_prediction_diagnostics", "seed": args.seed,
               "resamples": args.resamples, "calendar_block_days": list(BLOCK_DAYS), "input_sha256": hashes,
               "limitations": ["Holdout is spent; no fresh validation or model refit.",
                   "Nonoverlapping calendar-cluster sensitivity does not resolve fitting uncertainty, recurrent-team dependence or new-season generalization.",
                   "Track A uses realized participation; only Track B is operational pregame.",
                   "Holdout calibration regressions/bins and existing subgroup flags are descriptive, not deployable routing rules.",
                   "Accounting and regularisation changed jointly; no isolated accounting effect.",
                   "Intervals are unadjusted exploratory comparisons; no multiplicity-controlled discovery claim."], "tracks": {}}
    for track in ("track_a", "track_b"):
        frame, params = load_track(package, track)
        results["tracks"][track] = analyse_track(frame, params, args.resamples, args.seed)
    after = {path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
    if after != hashes:
        raise RuntimeError("input bytes changed while analysing")
    output.mkdir(parents=True, exist_ok=True)
    (output / "supplement_results.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# PMI saved-forecast supplement", "", "All analyses below are post hoc, conditional on the saved fitted forecasts.", "",
             "## Operational Track B", "", "| Model | RMSE | MAE | MSE | 80% coverage | Width | Interval score |", "|---|---:|---:|---:|---:|---:|---:|"]
    metrics = results["tracks"]["track_b"]["variants"]["as_frozen"]["metrics"]
    for model in MODELS:
        m = metrics[model]
        lines.append(f"| {model} | {m['rmse']:.6f} | {m['mae']:.6f} | {m['mse']:.6f} | {m['coverage_80']:.4f} | {m['mean_interval_width']:.4f} | {m['interval_score_80']:.4f} |")
    lines += ["", "## Calendar-cluster sensitivity", "", "Seed and all 7/14/28-day results are retained in the JSON. Season game weights stay fixed. Differences are candidate minus comparator.", "",
              "| Variant | Block days | Contrast | RMSE difference | Exploratory 95% interval |", "|---|---:|---|---:|---|"]
    for variant, result in results["tracks"]["track_b"]["variants"].items():
        for days, block in result["calendar_cluster_sensitivity"].items():
            for contrast, values in block["contrasts"].items():
                lo, hi = values["rmse_percentile_95"]
                lines.append(f"| {variant} | {days} | {contrast} | {values['rmse_difference']:+.6f} | [{lo:+.6f}, {hi:+.6f}] |")
    lines += ["", "## Limits", ""] + [f"- {limit}" for limit in results["limitations"]]
    (output / "SUPPLEMENT_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("OK: both tracks analysed; input hashes unchanged; results explicitly post hoc")


if __name__ == "__main__":
    main()
