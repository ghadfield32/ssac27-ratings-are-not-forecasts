"""
RAPM EDA Module -- Pre-fitting analysis of stint quality and data characteristics.

Following the GBDT/Bayesian pipeline EDA pattern:
  1. Target distribution (net_rating_per_100)
  2. Stint count distribution per season
  3. Possessions per player
  4. Lineup overlap / collinearity
  5. Season-over-season player overlap
  6. BPM correlation readiness check
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional

from ..config import RapmPipelineConfig


def run_stint_eda(
    stints_df: pd.DataFrame,
    config: RapmPipelineConfig,
    season: str = None,
) -> dict:
    """Run EDA on stint data before RAPM fitting.

    Parameters
    ----------
    stints_df : pd.DataFrame
        Stint-level data from stint_aggregator.
    config : RapmPipelineConfig
        Pipeline configuration.
    season : str, optional
        Season label for output.

    Returns
    -------
    dict with EDA results.
    """
    results = {
        "season": season or "unknown",
        "n_stints": len(stints_df),
        "n_games": stints_df["game_id"].nunique() if "game_id" in stints_df.columns else 0,
    }

    if len(stints_df) == 0:
        print("WARNING: No stints to analyze")
        return results

    # 1. Target distribution
    nr = stints_df["net_rating_per_100"]
    results["net_rating"] = {
        "mean": float(nr.mean()),
        "std": float(nr.std()),
        "median": float(nr.median()),
        "min": float(nr.min()),
        "max": float(nr.max()),
        "skew": float(nr.skew()),
        "kurtosis": float(nr.kurtosis()),
    }

    print(f"\n=== STINT EDA: {season or 'all'} ===")
    print(f"Stints: {len(stints_df):,}")
    print(f"Games: {results['n_games']:,}")
    print(f"Net rating: mean={nr.mean():.2f}, std={nr.std():.2f}, range=[{nr.min():.0f}, {nr.max():.0f}]")

    # 2. Possession distribution
    poss = stints_df["possessions"]
    results["possessions"] = {
        "mean": float(poss.mean()),
        "std": float(poss.std()),
        "median": float(poss.median()),
        "total": int(poss.sum()),
        "pct_single_poss": float((poss == 1).mean()),
    }
    print(f"Possessions per stint: mean={poss.mean():.1f}, median={poss.median():.0f}")
    print(f"Total possessions: {poss.sum():,}")

    # 3. Player participation
    all_players = set()
    player_poss = {}
    player_stints = {}

    for _, stint in stints_df.iterrows():
        home = stint["home_lineup"]
        away = stint["away_lineup"]
        n_poss = stint["possessions"]

        for lineup in [home, away]:
            if lineup is not None:
                for pid in lineup:
                    pid = int(pid)
                    all_players.add(pid)
                    player_poss[pid] = player_poss.get(pid, 0) + n_poss
                    player_stints[pid] = player_stints.get(pid, 0) + 1

    poss_arr = np.array(list(player_poss.values()))
    stints_arr = np.array(list(player_stints.values()))

    results["players"] = {
        "total": len(all_players),
        "with_min_poss": int((poss_arr >= config.min_poss_per_player).sum()),
        "poss_per_player_mean": float(poss_arr.mean()),
        "poss_per_player_median": float(np.median(poss_arr)),
        "poss_per_player_min": int(poss_arr.min()),
        "poss_per_player_max": int(poss_arr.max()),
        "stints_per_player_mean": float(stints_arr.mean()),
    }

    print(f"Players: {len(all_players)}")
    print(f"Players with >={config.min_poss_per_player} poss: {(poss_arr >= config.min_poss_per_player).sum()}")
    print(f"Possessions per player: mean={poss_arr.mean():.0f}, median={np.median(poss_arr):.0f}")

    # 4. Lineup overlap / collinearity indicator
    # Count how many distinct 5-man lineups appear
    home_lineups = set()
    for lineup in stints_df["home_lineup"]:
        if lineup is not None:
            home_lineups.add(tuple(sorted(int(p) for p in lineup)))

    away_lineups = set()
    for lineup in stints_df["away_lineup"]:
        if lineup is not None:
            away_lineups.add(tuple(sorted(int(p) for p in lineup)))

    all_lineups = home_lineups | away_lineups
    results["lineups"] = {
        "unique_5man": len(all_lineups),
        "unique_home": len(home_lineups),
        "unique_away": len(away_lineups),
        "lineup_to_stint_ratio": len(all_lineups) / max(len(stints_df), 1),
    }
    print(f"Unique 5-man lineups: {len(all_lineups)}")
    print(f"Lineup/stint ratio: {len(all_lineups) / max(len(stints_df), 1):.3f}")

    # 5. Quality assessment
    passes_stint_count = len(stints_df) >= config.min_stints_per_season
    results["quality"] = {
        "passes_min_stints": passes_stint_count,
        "min_stints_threshold": config.min_stints_per_season,
        "near_zero_mean": abs(nr.mean()) < 5.0,
    }

    status = "PASS" if passes_stint_count else "WARN"
    print(f"\nQuality: {status}")
    print(f"  Min stints ({config.min_stints_per_season:,}): {'PASS' if passes_stint_count else 'FAIL'} ({len(stints_df):,})")
    print(f"  Near-zero mean: {'PASS' if abs(nr.mean()) < 5.0 else 'FAIL'} ({nr.mean():.2f})")

    return results


def run_multi_season_eda(
    season_stints: Dict[str, pd.DataFrame],
    config: RapmPipelineConfig,
) -> dict:
    """Run EDA across multiple seasons.

    Parameters
    ----------
    season_stints : dict
        Mapping from season string to stint DataFrame.
    config : RapmPipelineConfig
        Pipeline configuration.

    Returns
    -------
    dict with per-season and cross-season EDA results.
    """
    results = {"seasons": {}}
    all_players_by_season = {}

    for season in sorted(season_stints.keys()):
        df = season_stints[season]
        season_result = run_stint_eda(df, config, season=season)
        results["seasons"][season] = season_result

        # Track players per season
        players = set()
        for _, stint in df.iterrows():
            for lineup in [stint["home_lineup"], stint["away_lineup"]]:
                if lineup is not None:
                    players.update(int(p) for p in lineup)
        all_players_by_season[season] = players

    # Cross-season overlap analysis
    sorted_seasons = sorted(all_players_by_season.keys())
    overlap_stats = []
    for i in range(1, len(sorted_seasons)):
        prev = all_players_by_season[sorted_seasons[i - 1]]
        curr = all_players_by_season[sorted_seasons[i]]
        overlap = len(prev & curr)
        overlap_pct = overlap / max(len(curr), 1)
        overlap_stats.append({
            "from": sorted_seasons[i - 1],
            "to": sorted_seasons[i],
            "overlap": overlap,
            "pct_of_current": round(overlap_pct, 3),
        })
        print(f"\nSeason overlap {sorted_seasons[i-1]} -> {sorted_seasons[i]}: "
              f"{overlap} players ({overlap_pct:.1%} of current)")

    results["cross_season_overlap"] = overlap_stats

    # Total unique players
    all_ever = set()
    for players in all_players_by_season.values():
        all_ever.update(players)
    results["total_unique_players"] = len(all_ever)
    print(f"\nTotal unique players across all seasons: {len(all_ever)}")

    return results


def save_eda_report(results: dict, output_path: Path) -> None:
    """Save EDA results to JSON.

    Parameters
    ----------
    results : dict
        EDA results from run_stint_eda or run_multi_season_eda.
    output_path : Path
        Output JSON path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nEDA report saved to {output_path}")
