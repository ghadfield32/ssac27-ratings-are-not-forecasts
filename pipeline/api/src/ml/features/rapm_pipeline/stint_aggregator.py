"""
Stint Aggregator -- Convert possessions to RAPM-ready stint observations.

A stint is a continuous stretch of play where the same 10 players are on court.
Possessions within the same stint are grouped and aggregated to:
  - net_points = home_points - away_points
  - possessions = count of possessions in the stint
  - net_rating_per_100 = net_points / possessions * 100

IMPORTANT: In possessions.parquet, offense_lineup = home_lineup always (see
infer_possessions.py line 67-68). The naming is misleading. We use the
scoring_team field (from Made Shot / Free Throw events) to determine who scored.

Vectorized implementation -- no iterrows().
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple

from .config import RapmPipelineConfig


def _build_player_team_map(stints_df: pd.DataFrame) -> Dict[Tuple[str, int], int]:
    """Build a (game_id, player_id) -> team_id mapping from rotation stints."""
    deduped = stints_df[["GAME_ID", "PLAYER_ID", "TEAM_ID"]].drop_duplicates()
    return dict(zip(
        zip(deduped["GAME_ID"], deduped["PLAYER_ID"]),
        deduped["TEAM_ID"],
    ))


def _lineup_to_key(lineup) -> str:
    """Convert a lineup (list/array of player IDs) to a hashable string key."""
    if lineup is None or (hasattr(lineup, '__len__') and len(lineup) == 0):
        return ""
    return ",".join(str(int(x)) for x in sorted(lineup))


def _key_to_lineup(key: str) -> list:
    """Convert a string key back to a list of player IDs."""
    if not key:
        return []
    return [int(x) for x in key.split(",")]


def aggregate_possessions_to_stints(
    poss_df: pd.DataFrame,
    stints_df: pd.DataFrame,
    config: RapmPipelineConfig,
    season: str = None,
) -> pd.DataFrame:
    """Aggregate possessions into stints for RAPM fitting.

    Fully vectorized -- no iterrows().

    Parameters
    ----------
    poss_df : pd.DataFrame
        Possessions data (from possessions.parquet).
    stints_df : pd.DataFrame
        Rotation stint data (from game_rotation_player_stint.parquet).
    config : RapmPipelineConfig
        Pipeline configuration.
    season : str, optional
        Season string (e.g. "2023-24").

    Returns
    -------
    pd.DataFrame
        Stint-level data with columns:
        game_id, stint_id, home_lineup, away_lineup, home_team_id, away_team_id,
        home_points, away_points, possessions, net_rating_per_100,
        duration_seconds, season
    """
    n_total = len(poss_df)
    print(f"Aggregating {n_total:,} possessions into stints...")

    # Build player -> team mapping (vectorized via dict comprehension)
    player_team_map = _build_player_team_map(stints_df)
    print(f"  Player-team mappings: {len(player_team_map):,}")

    # -- Step 1: Determine home_team_id and away_team_id per game --------
    # offense_lineup = home_lineup always; use first player to find home team
    game_home_team = {}
    game_away_team = {}

    for game_id, game_poss in poss_df.groupby("gameId"):
        first = game_poss.iloc[0]
        off_lineup = first["offense_lineup"]
        def_lineup = first["defense_lineup"]

        if off_lineup is not None and len(off_lineup) >= 1:
            pid = int(off_lineup[0])
            home_tid = player_team_map.get((game_id, pid))
            if home_tid is not None:
                game_home_team[game_id] = home_tid

        if def_lineup is not None and len(def_lineup) >= 1:
            pid = int(def_lineup[0])
            away_tid = player_team_map.get((game_id, pid))
            if away_tid is not None and away_tid != game_home_team.get(game_id):
                game_away_team[game_id] = away_tid

    n_games = poss_df["gameId"].nunique()
    print(f"  Games with home team: {len(game_home_team):,} / {n_games}")

    # -- Step 2: Map home/away team to each possession (vectorized) ------
    df = poss_df.copy()
    df["home_team_id"] = df["gameId"].map(game_home_team)
    df["away_team_id"] = df["gameId"].map(game_away_team).fillna(0).astype(int)

    # Filter: valid lineups + known home team
    df["off_len"] = df["offense_lineup"].apply(
        lambda x: len(x) if x is not None and hasattr(x, '__len__') else 0
    )
    df["def_len"] = df["defense_lineup"].apply(
        lambda x: len(x) if x is not None and hasattr(x, '__len__') else 0
    )
    valid = (df["off_len"] == 5) & (df["def_len"] == 5) & df["home_team_id"].notna()
    skipped = (~valid).sum()
    df = df[valid].copy()

    # -- Step 3: Attribute points to home/away (vectorized) ---------------
    pts = df["points_scored"].fillna(0).astype(int)
    scoring_team = df.get("scoring_team", pd.Series(dtype=float))
    offense_team = df.get("offense_team", pd.Series(dtype=float))
    home_tid = df["home_team_id"].astype(int)

    # scoring_team is primary signal
    has_scoring = scoring_team.notna() & (scoring_team > 0)
    scoring_is_home = has_scoring & (scoring_team.astype(float).astype("Int64") == home_tid)

    # offense_team is fallback
    has_offense_only = ~has_scoring & offense_team.notna() & (offense_team > 0) & (pts > 0)
    offense_is_home = has_offense_only & (offense_team.astype(float).astype("Int64") == home_tid)

    # Compute home/away points
    df["home_points"] = 0
    df["away_points"] = 0

    # scoring_team -> home
    mask_home_score = scoring_is_home & (pts > 0)
    mask_away_score = has_scoring & ~scoring_is_home & (pts > 0)
    df.loc[mask_home_score, "home_points"] = pts[mask_home_score]
    df.loc[mask_away_score, "away_points"] = pts[mask_away_score]

    # offense_team fallback -> home
    df.loc[offense_is_home, "home_points"] = pts[offense_is_home]
    df.loc[has_offense_only & ~offense_is_home, "away_points"] = pts[has_offense_only & ~offense_is_home]

    resolved_scoring = (has_scoring & (pts > 0)).sum()
    resolved_offense = has_offense_only.sum()
    resolved_zero = ((pts == 0) | (~has_scoring & ~has_offense_only)).sum()

    print(f"  Possessions mapped: {len(df):,} (skipped: {skipped})")
    print(f"  Scoring resolved: scoring_team={resolved_scoring:,}, "
          f"offense_team_fallback={resolved_offense:,}, "
          f"zero_pts={resolved_zero:,}")

    if len(df) == 0:
        return pd.DataFrame()

    # Sanity check
    total_home = df["home_points"].sum()
    total_away = df["away_points"].sum()
    print(f"  Total points: home={total_home:,.0f}, away={total_away:,.0f}, "
          f"diff={total_home - total_away:+,.0f}")
    print(f"  Points per possession: "
          f"{(total_home + total_away) / max(len(df), 1):.3f}")

    # -- Step 4: Create lineup keys for grouping -------------------------
    df["home_lineup_key"] = df["offense_lineup"].apply(_lineup_to_key)
    df["away_lineup_key"] = df["defense_lineup"].apply(_lineup_to_key)

    # Handle duration NaN
    df["duration_val"] = df["duration"].fillna(0.0).astype(float)
    negative_duration = df["duration_val"] < 0
    if negative_duration.any():
        sample = df.loc[
            negative_duration,
            ["gameId", "possession_id", "start_time", "end_time", "duration_val", "outcome"],
        ].head(10)
        raise ValueError(
            "[RAPM] Negative possession durations detected before stint aggregation. "
            f"count={int(negative_duration.sum())}\n{sample.to_string(index=False)}"
        )

    # -- Step 5: Group into stints and aggregate -------------------------
    grouped = df.groupby(["gameId", "home_lineup_key", "away_lineup_key"]).agg(
        possessions=("home_points", "size"),
        home_points=("home_points", "sum"),
        away_points=("away_points", "sum"),
        duration_seconds=("duration_val", "sum"),
        home_team_id=("home_team_id", "first"),
        away_team_id=("away_team_id", "first"),
    ).reset_index()

    # Filter by minimum possessions
    grouped = grouped[grouped["possessions"] >= config.min_poss_per_stint].copy()

    # Compute net rating
    grouped["net_points"] = grouped["home_points"] - grouped["away_points"]
    grouped["net_rating_per_100"] = grouped["net_points"] / grouped["possessions"] * 100.0

    # Convert lineup keys back to lists
    grouped["home_lineup"] = grouped["home_lineup_key"].apply(_key_to_lineup)
    grouped["away_lineup"] = grouped["away_lineup_key"].apply(_key_to_lineup)

    # Rename and select columns
    grouped["game_id"] = grouped["gameId"]
    grouped["stint_id"] = range(len(grouped))
    grouped["season"] = season
    grouped["home_team_id"] = grouped["home_team_id"].astype(int)
    grouped["away_team_id"] = grouped["away_team_id"].astype(int)

    result = grouped[[
        "game_id", "stint_id", "home_lineup", "away_lineup",
        "home_team_id", "away_team_id",
        "home_points", "away_points", "net_points",
        "possessions", "net_rating_per_100",
        "duration_seconds", "season",
    ]].copy()

    print(f"  Stints created: {len(result):,}")
    if len(result) > 0:
        print(f"  Possessions per stint: mean={result['possessions'].mean():.1f}, "
              f"median={result['possessions'].median():.0f}")
        print(f"  Net rating: mean={result['net_rating_per_100'].mean():.2f}, "
              f"std={result['net_rating_per_100'].std():.2f}")

    return result
