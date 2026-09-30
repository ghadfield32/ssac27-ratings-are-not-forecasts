"""
Sparse Design Matrix Builder for RAPM.

Builds a scipy.sparse.csr_matrix where:
  - Each row = one stint
  - Each column = one player
  - +1 for home team players, -1 for away team players
  - Weight vector = possession count per stint (with optional time decay)

This replaces the old dense np.zeros approach which was O(n_stints * n_players)
in memory. Sparse representation is essential for 500+ players x 100K+ stints.
"""

import numpy as np
import pandas as pd
import scipy.sparse as sp
from typing import Dict, List, Tuple


def build_player_index(stints_df: pd.DataFrame) -> Dict[int, int]:
    """Build a mapping from player_id to column index.

    Parameters
    ----------
    stints_df : pd.DataFrame
        Stint data with home_lineup and away_lineup columns (lists of ints).

    Returns
    -------
    Dict mapping player_id -> column_index (0-based, sorted).
    """
    all_players = set()
    for lineup in stints_df["home_lineup"]:
        if lineup is not None:
            all_players.update(int(p) for p in lineup)
    for lineup in stints_df["away_lineup"]:
        if lineup is not None:
            all_players.update(int(p) for p in lineup)

    sorted_players = sorted(all_players)
    return {pid: idx for idx, pid in enumerate(sorted_players)}


def build_sparse_design_matrix(
    stints_df: pd.DataFrame,
    player_index: Dict[int, int],
) -> Tuple[sp.csr_matrix, np.ndarray, np.ndarray]:
    """Build sparse RAPM design matrix from stint data.

    Parameters
    ----------
    stints_df : pd.DataFrame
        Stint data with home_lineup, away_lineup, net_rating_per_100, possessions.
    player_index : dict
        Mapping from player_id to column index.

    Returns
    -------
    Tuple of (X, y, weights):
        X : scipy.sparse.csr_matrix, shape (n_stints, n_players)
            +1 for home players, -1 for away players.
        y : np.ndarray, shape (n_stints,)
            Target: net_rating_per_100.
        weights : np.ndarray, shape (n_stints,)
            Sample weights: number of possessions per stint.
    """
    n_stints = len(stints_df)
    n_players = len(player_index)

    # COO format for efficient construction
    row_indices = []
    col_indices = []
    data_values = []

    y = np.zeros(n_stints)
    weights = np.zeros(n_stints)

    for i, (_, stint) in enumerate(stints_df.iterrows()):
        # Home players: +1
        home_lineup = stint["home_lineup"]
        if home_lineup is not None:
            for pid in home_lineup:
                pid = int(pid)
                if pid in player_index:
                    row_indices.append(i)
                    col_indices.append(player_index[pid])
                    data_values.append(1.0)

        # Away players: -1
        away_lineup = stint["away_lineup"]
        if away_lineup is not None:
            for pid in away_lineup:
                pid = int(pid)
                if pid in player_index:
                    row_indices.append(i)
                    col_indices.append(player_index[pid])
                    data_values.append(-1.0)

        y[i] = stint["net_rating_per_100"]
        weights[i] = stint["possessions"]

    X = sp.coo_matrix(
        (data_values, (row_indices, col_indices)),
        shape=(n_stints, n_players),
    ).tocsr()

    return X, y, weights


def build_multi_season_matrix(
    season_stints: Dict[str, pd.DataFrame],
    target_season: str,
    decay_factor: float = 0.80,
) -> Tuple[sp.csr_matrix, np.ndarray, np.ndarray, Dict[int, int]]:
    """Build multi-season design matrix with time decay.

    Pools stints from multiple seasons, weighting older seasons less.

    Parameters
    ----------
    season_stints : dict
        Mapping from season string to stint DataFrame.
    target_season : str
        The most recent season (gets decay^0 = 1.0 weight).
    decay_factor : float
        Per-season decay factor. Season N-1 gets weight decay^1, N-2 gets decay^2, etc.

    Returns
    -------
    Tuple of (X, y, weights, player_index):
        X : scipy.sparse.csr_matrix
        y : np.ndarray
        weights : np.ndarray (includes decay)
        player_index : Dict[int, int]
    """
    # Sort seasons chronologically
    sorted_seasons = sorted(season_stints.keys())
    target_idx = sorted_seasons.index(target_season) if target_season in sorted_seasons else len(sorted_seasons) - 1

    # Concatenate all stints with decay weights
    all_stints = []
    decay_multipliers = []

    for season in sorted_seasons:
        df = season_stints[season].copy()
        seasons_ago = target_idx - sorted_seasons.index(season)
        decay = decay_factor ** seasons_ago

        all_stints.append(df)
        decay_multipliers.extend([decay] * len(df))

    combined = pd.concat(all_stints, ignore_index=True)
    decay_arr = np.array(decay_multipliers)

    # Build unified player index
    player_index = build_player_index(combined)

    # Build design matrix
    X, y, base_weights = build_sparse_design_matrix(combined, player_index)

    # Apply decay to weights: final_weight = possessions * decay^seasons_ago
    final_weights = base_weights * decay_arr

    return X, y, final_weights, player_index
