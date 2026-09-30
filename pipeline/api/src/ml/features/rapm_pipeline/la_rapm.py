"""
LA-RAPM Core Fitting Module.

Fits Luck-Adjusted Regularized Adjusted Plus-Minus using Ridge regression
with multi-season pooling, possession weighting, and time decay.

Standard formulation:
  y_stint = sum(beta_i for i in home_lineup)
          - sum(beta_j for j in away_lineup)
          + intercept + epsilon

  Regularization: Ridge (L2) with lambda in [2000, 5000]
  Weighting: possessions * decay^seasons_ago
"""

import numpy as np
import pandas as pd
from typing import Dict

from sklearn.linear_model import Ridge

from .config import RapmPipelineConfig
from .design_matrix import (
    build_player_index,
    build_sparse_design_matrix,
    build_multi_season_matrix,
)


def fit_single_season_rapm(
    stints_df: pd.DataFrame,
    config: RapmPipelineConfig,
) -> pd.DataFrame:
    """Fit RAPM for a single season of stint data.

    Parameters
    ----------
    stints_df : pd.DataFrame
        Stint data for one season.
    config : RapmPipelineConfig
        Pipeline configuration.

    Returns
    -------
    pd.DataFrame with columns: PLAYER_ID, RAPM_NET, N_STINTS, TOTAL_POSS
    """
    player_index = build_player_index(stints_df)
    X, y, weights = build_sparse_design_matrix(stints_df, player_index)

    print(f"  Design matrix: {X.shape[0]:,} stints x {X.shape[1]:,} players")
    print(f"  Non-zero entries: {X.nnz:,} ({X.nnz / (X.shape[0] * X.shape[1]):.3%} dense)")
    print(f"  Target range: [{y.min():.1f}, {y.max():.1f}], mean={y.mean():.2f}")

    # Fit Ridge regression
    model = Ridge(alpha=config.lambda_reg, fit_intercept=config.fit_intercept)
    model.fit(X, y, sample_weight=weights)

    print(f"  Intercept: {model.intercept_:.3f}")
    print(f"  Coef range: [{model.coef_.min():.3f}, {model.coef_.max():.3f}]")

    # Build results
    inv_index = {idx: pid for pid, idx in player_index.items()}
    results = []
    for idx in range(len(player_index)):
        pid = inv_index[idx]
        # Count stints and possessions for this player
        col = X.getcol(idx).toarray().flatten()
        mask = col != 0
        n_stints = mask.sum()
        total_poss = weights[mask].sum()

        results.append({
            "PLAYER_ID": pid,
            "RAPM_NET": model.coef_[idx],
            "N_STINTS": int(n_stints),
            "TOTAL_POSS": int(total_poss),
        })

    return pd.DataFrame(results)


def fit_multi_season_rapm(
    season_stints: Dict[str, pd.DataFrame],
    target_season: str,
    config: RapmPipelineConfig,
) -> pd.DataFrame:
    """Fit multi-season LA-RAPM with time decay.

    Parameters
    ----------
    season_stints : dict
        Mapping from season string to stint DataFrame.
    target_season : str
        The most recent season (anchor for decay).
    config : RapmPipelineConfig
        Pipeline configuration.

    Returns
    -------
    pd.DataFrame with columns: PLAYER_ID, SEASON, RAPM_NET, N_STINTS, TOTAL_POSS
    """
    seasons_used = sorted(season_stints.keys())
    total_stints = sum(len(df) for df in season_stints.values())
    print(f"  Multi-season RAPM: {len(seasons_used)} seasons, {total_stints:,} total stints")
    print(f"  Seasons: {seasons_used}")
    print(f"  Target season: {target_season}, decay={config.decay_factor}")

    X, y, weights, player_index = build_multi_season_matrix(
        season_stints, target_season, config.decay_factor
    )

    print(f"  Design matrix: {X.shape[0]:,} stints x {X.shape[1]:,} players")
    print(f"  Non-zero entries: {X.nnz:,} ({X.nnz / (X.shape[0] * X.shape[1]):.3%} dense)")

    # Fit Ridge regression
    model = Ridge(alpha=config.lambda_reg, fit_intercept=config.fit_intercept)
    model.fit(X, y, sample_weight=weights)

    print(f"  Intercept: {model.intercept_:.3f}")
    print(f"  Coef range: [{model.coef_.min():.3f}, {model.coef_.max():.3f}]")

    # Build results
    inv_index = {idx: pid for pid, idx in player_index.items()}
    results = []
    for idx in range(len(player_index)):
        pid = inv_index[idx]
        col = X.getcol(idx).toarray().flatten()
        mask = col != 0
        n_stints = mask.sum()
        total_poss = weights[mask].sum()

        results.append({
            "PLAYER_ID": pid,
            "SEASON": target_season,
            "RAPM_NET": model.coef_[idx],
            "N_STINTS": int(n_stints),
            "TOTAL_POSS": int(total_poss),
        })

    return pd.DataFrame(results)


def fit_offensive_defensive_rapm(
    stints_df: pd.DataFrame,
    config: RapmPipelineConfig,
) -> pd.DataFrame:
    """Fit separate offensive and defensive RAPM for a single season.

    Uses possession-level data to fit two models:
    1. Offensive: predicts home team points scored per 100 possessions
    2. Defensive: predicts away team points allowed per 100 possessions

    If stints_df contains luck-adjustment columns (luck_home_3p, luck_home_ft,
    luck_away_3p, luck_away_ft), the offense/defense targets are luck-adjusted
    before fitting.

    Parameters
    ----------
    stints_df : pd.DataFrame
        Stint data with home_points, away_points, possessions columns.
    config : RapmPipelineConfig
        Pipeline configuration.

    Returns
    -------
    pd.DataFrame with PLAYER_ID, RAPM_OFFENSE, RAPM_DEFENSE, RAPM_NET,
    N_STINTS, TOTAL_POSS
    """
    player_index = build_player_index(stints_df)
    X, _, weights = build_sparse_design_matrix(stints_df, player_index)

    # Use luck-adjusted points if available (from build_luck_neutral_stints.py)
    has_luck = "luck_home_3p" in stints_df.columns
    if has_luck:
        home_pts = (
            stints_df["home_points"]
            - stints_df["luck_home_3p"]
            - stints_df["luck_home_ft"]
        ).values
        away_pts = (
            stints_df["away_points"]
            - stints_df["luck_away_3p"]
            - stints_df["luck_away_ft"]
        ).values
        print("  Using luck-adjusted OD targets (luck columns present)")
    else:
        home_pts = stints_df["home_points"].values
        away_pts = stints_df["away_points"].values

    poss = stints_df["possessions"].values
    y_off = (home_pts / poss) * 100.0
    y_def = (away_pts / poss) * 100.0

    # Fit offensive model
    model_off = Ridge(alpha=config.lambda_reg, fit_intercept=config.fit_intercept)
    model_off.fit(X, y_off, sample_weight=weights)

    # Fit defensive model (negative sign: +1 for home players means LESS points allowed)
    model_def = Ridge(alpha=config.lambda_reg, fit_intercept=config.fit_intercept)
    model_def.fit(X, y_def, sample_weight=weights)

    # Build results
    inv_index = {idx: pid for pid, idx in player_index.items()}
    results = []
    for idx in range(len(player_index)):
        pid = inv_index[idx]
        col = X.getcol(idx).toarray().flatten()
        mask = col != 0
        n_stints = mask.sum()
        total_poss = weights[mask].sum()

        o_rapm = model_off.coef_[idx]
        # Negate: positive d_rapm = fewer points allowed = good defense
        d_rapm = -model_def.coef_[idx]

        results.append({
            "PLAYER_ID": pid,
            "RAPM_OFFENSE": o_rapm,
            "RAPM_DEFENSE": d_rapm,
            "RAPM_NET": o_rapm + d_rapm,
            "N_STINTS": int(n_stints),
            "TOTAL_POSS": int(total_poss),
        })

    return pd.DataFrame(results)


def fit_multi_season_od_rapm(
    season_stints: Dict[str, pd.DataFrame],
    target_season: str,
    config: RapmPipelineConfig,
) -> pd.DataFrame:
    """Fit multi-season offensive and defensive RAPM with time decay.

    Pools stints across seasons (weighted by decay^seasons_ago) and fits
    separate Ridge models for offense (RAPM_OFFENSE) and defense (RAPM_DEFENSE).

    If stints contain luck-adjustment columns (luck_home_3p etc.), the offense
    and defense targets are luck-adjusted before fitting.

    Parameters
    ----------
    season_stints : dict
        Mapping from season string to stint DataFrame.
    target_season : str
        The most recent season (anchor for decay, stored in SEASON column).
    config : RapmPipelineConfig
        Pipeline configuration.

    Returns
    -------
    pd.DataFrame with PLAYER_ID, SEASON, RAPM_OFFENSE, RAPM_DEFENSE,
    RAPM_NET, N_STINTS, TOTAL_POSS
    """
    sorted_seasons = sorted(season_stints.keys())
    if target_season in sorted_seasons:
        target_idx = sorted_seasons.index(target_season)
    else:
        target_idx = len(sorted_seasons) - 1

    total_stints = sum(len(df) for df in season_stints.values())
    print(
        f"  Multi-season OD RAPM: {len(sorted_seasons)} seasons, "
        f"{total_stints:,} total stints"
    )
    print(f"  Seasons: {sorted_seasons}")
    print(f"  Target season: {target_season}, decay={config.decay_factor}")

    # Concatenate stints with time decay (same ordering as build_multi_season_matrix)
    all_dfs = []
    decay_multipliers = []
    for season in sorted_seasons:
        df = season_stints[season].copy()
        seasons_ago = target_idx - sorted_seasons.index(season)
        decay = config.decay_factor ** seasons_ago
        all_dfs.append(df)
        decay_multipliers.extend([decay] * len(df))

    combined = pd.concat(all_dfs, ignore_index=True)
    decay_arr = np.array(decay_multipliers)

    # Build unified design matrix
    player_index = build_player_index(combined)
    X, _, base_weights = build_sparse_design_matrix(combined, player_index)
    final_weights = base_weights * decay_arr

    print(f"  Design matrix: {X.shape[0]:,} stints x {X.shape[1]:,} players")
    print(f"  Non-zero entries: {X.nnz:,} ({X.nnz / (X.shape[0] * X.shape[1]):.3%} dense)")

    # Compute offense/defense targets — use luck-adjusted if available
    has_luck = "luck_home_3p" in combined.columns
    if has_luck:
        home_pts = (
            combined["home_points"]
            - combined["luck_home_3p"]
            - combined["luck_home_ft"]
        ).values
        away_pts = (
            combined["away_points"]
            - combined["luck_away_3p"]
            - combined["luck_away_ft"]
        ).values
        print("  Using luck-adjusted OD targets")
    else:
        home_pts = combined["home_points"].values
        away_pts = combined["away_points"].values
        print("  Using raw OD targets (no luck columns)")

    poss = combined["possessions"].values
    y_off = (home_pts / poss) * 100.0
    y_def = (away_pts / poss) * 100.0

    # Fit offensive model
    model_off = Ridge(alpha=config.lambda_reg, fit_intercept=config.fit_intercept)
    model_off.fit(X, y_off, sample_weight=final_weights)
    print(
        f"  Offense intercept: {model_off.intercept_:.3f}, "
        f"coef range: [{model_off.coef_.min():.3f}, {model_off.coef_.max():.3f}]"
    )

    # Fit defensive model
    model_def = Ridge(alpha=config.lambda_reg, fit_intercept=config.fit_intercept)
    model_def.fit(X, y_def, sample_weight=final_weights)
    print(
        f"  Defense intercept: {model_def.intercept_:.3f}, "
        f"coef range: [{model_def.coef_.min():.3f}, {model_def.coef_.max():.3f}]"
    )

    # Build results
    inv_index = {idx: pid for pid, idx in player_index.items()}
    results = []
    for idx in range(len(player_index)):
        pid = inv_index[idx]
        col = X.getcol(idx).toarray().flatten()
        mask = col != 0
        n_stints = mask.sum()
        total_poss = final_weights[mask].sum()

        o_rapm = model_off.coef_[idx]
        # Negate: positive d_rapm = fewer points allowed = good defense
        d_rapm = -model_def.coef_[idx]

        results.append({
            "PLAYER_ID": pid,
            "SEASON": target_season,
            "RAPM_OFFENSE": o_rapm,
            "RAPM_DEFENSE": d_rapm,
            "RAPM_NET": o_rapm + d_rapm,
            "N_STINTS": int(n_stints),
            "TOTAL_POSS": int(total_poss),
        })

    return pd.DataFrame(results)
