#!/usr/bin/env python3
"""
Vectorized PBP -> lineup linking.

10-50x faster than the original per-event iteration in link_pbp_to_stints.py.
For each game, uses numpy broadcasting to find which players are on court at
each event time, avoiding Python for-loops.
"""

import sys
import json
import gzip
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nba_value.data.link_pbp_to_stints import parse_clock_to_seconds


# ---- CDN current-season PBP taxonomy normalization ----
# Older-season bronze (stats.nba.com) uses the canonical action taxonomy
# ("Made Shot"/"Missed Shot"/"Free Throw"/"Rebound"/...) with a `shotValue`
# column. The cdn.nba.com current-season feed switched to a granular lowercase
# taxonomy ("2pt"/"3pt"/"freethrow"/"rebound"/...) carrying `shotResult` instead
# of `shotValue`. Downstream possession inference (infer_possessions) and the
# simulation event table (event_table_builder) both parse the canonical
# taxonomy, so the cdn feed is normalized to canonical here at the single
# bronze->silver linking edge. No-op when the feed is already canonical.
_CDN_TO_CANONICAL_ACTION = {
    "rebound": "Rebound",
    "turnover": "Turnover",
    "foul": "Foul",
    "substitution": "Substitution",
    "timeout": "Timeout",
    "jumpball": "Jump Ball",
    "freethrow": "Free Throw",
    "violation": "Violation",
    "ejection": "Ejection",
}


def _normalize_cdn_taxonomy(pbp_df: pd.DataFrame) -> pd.DataFrame:
    """Map the cdn.nba.com current-season PBP taxonomy to the canonical
    stats.nba.com taxonomy. No-op for already-canonical (older-season) feeds.

    Detected per game by the lowercase shot tokens ("2pt"/"3pt"/"freethrow").
    When present: shots become Made/Missed Shot with a derived shotValue (2/3),
    the remaining lowercase action types are mapped to canonical TitleCase, and
    shooting fouls are mapped from the cdn `descriptor` to the canonical subType
    ("Shooting"/"Charge"). Every other field the cdn feed already carries
    (shotResult, xLegacy/yLegacy, scoreHome/scoreAway, personId, pointsTotal) is
    left untouched -- downstream parsers derive shot-made from shotResult and
    offensive-rebound from next-event lookahead, not from rebound/FT subType.
    """
    if "actionType" not in pbp_df.columns:
        return pbp_df
    at = pbp_df["actionType"].astype(str)
    if not at.isin(("2pt", "3pt", "freethrow")).any():
        return pbp_df  # already canonical -> no-op

    df = pbp_df.copy()
    sr = df["shotResult"].astype(str) if "shotResult" in df.columns \
        else pd.Series("", index=df.index)
    is_2pt, is_3pt = (at == "2pt"), (at == "3pt")
    is_shot = is_2pt | is_3pt
    made, missed = (sr == "Made"), (sr == "Missed")

    # shotValue derived from the action token (canonical feed carries this column)
    if "shotValue" not in df.columns:
        df["shotValue"] = np.nan
    df.loc[is_2pt, "shotValue"] = 2
    df.loc[is_3pt, "shotValue"] = 3

    # actionType -> canonical. Downstream derives shot-made from shotResult and
    # offensive-rebound from next-event lookahead (event_table_builder) -- NOT from
    # subType -- and both feeds carry shotResult, so subType is left exactly as the
    # source provides it (canonical "Unknown"/"Free Throw 1 of 2"; cdn "defensive"/
    # "1 of 2"). This avoids inventing subType conventions that would diverge from
    # the canonical seasons.
    df.loc[is_shot & made, "actionType"] = "Made Shot"
    df.loc[is_shot & missed, "actionType"] = "Missed Shot"
    for cdn_at, canon in _CDN_TO_CANONICAL_ACTION.items():
        df.loc[at == cdn_at, "actionType"] = canon

    # Shooting fouls ARE meaningfully encoded in the canonical subType
    # ("Shooting"/"Charge", per event_table_builder.SHOOTING_FOUL_SUBTYPES); the
    # cdn feed carries the same distinction in the `descriptor` column. Map it so
    # cdn fouls classify identically to the canonical seasons. (Rebound/free-throw
    # subType is NOT mapped because the canonical feed carries no outcome there.)
    if "descriptor" in df.columns and "subType" in df.columns:
        desc = df["descriptor"].astype(str)
        is_foul = at == "foul"
        df.loc[is_foul & (desc == "shooting"), "subType"] = "Shooting"
        df.loc[is_foul & (desc == "charge"), "subType"] = "Charge"
    return df


def link_game_vectorized(
    pbp_df: pd.DataFrame,
    game_stints: pd.DataFrame,
    game_id: str,
) -> pd.DataFrame:
    """Vectorized lineup linking for a single game.

    For each team, builds a (n_events x n_stints) boolean containment matrix
    using numpy broadcasting, then extracts the 5 players on court at each event.
    """
    if len(game_stints) == 0:
        return pd.DataFrame()

    # Home/away team IDs
    team_ids = game_stints["TEAM_ID"].unique()
    if len(team_ids) < 2:
        return pd.DataFrame()

    home_team_id = game_stints["TEAM_ID"].mode().iloc[0]
    away_team_id = team_ids[team_ids != home_team_id][0]

    # Convert stint times
    game_stints = game_stints.copy()
    game_stints["IN_SEC"] = game_stints["IN_TIME_REAL"] / 10.0
    game_stints["OUT_SEC"] = game_stints["OUT_TIME_REAL"] / 10.0

    event_times = pbp_df["event_time"].values.astype(np.float64)
    n_events = len(event_times)

    # Process each team
    lineups = {}
    for team_label, tid in [("home", home_team_id), ("away", away_team_id)]:
        team_stints = game_stints[game_stints["TEAM_ID"] == tid]
        in_times = team_stints["IN_SEC"].values.astype(np.float64)
        out_times = team_stints["OUT_SEC"].values.astype(np.float64)
        player_ids = team_stints["PLAYER_ID"].values

        # Broadcasting: (n_events, n_stints)
        # True where event_time falls within [IN_SEC, OUT_SEC)
        in_range = (event_times[:, None] >= in_times[None, :]) & \
                   (event_times[:, None] < out_times[None, :])

        # For each event, collect on-court players
        event_lineups = []
        for i in range(n_events):
            on_court = player_ids[in_range[i]]
            if len(on_court) == 5:
                event_lineups.append(sorted(on_court.tolist()))
            else:
                event_lineups.append([])

        lineups[team_label] = event_lineups

    # Build output
    pbp_dict = pbp_df.to_dict("records")
    results = []
    for i in range(n_events):
        h = lineups["home"][i]
        a = lineups["away"][i]
        row = pbp_dict[i].copy()
        row["home_lineup"] = h
        row["away_lineup"] = a
        row["lineup_valid"] = len(h) == 5 and len(a) == 5
        results.append(row)

    return pd.DataFrame(results)


def process_season_vectorized(
    season: str,
    stints_df: pd.DataFrame,
    pbp_bronze_dir: Path,
    max_games: Optional[int] = None,
) -> pd.DataFrame:
    """Process all games in a season using vectorized linking.

    Parameters
    ----------
    season : str
        Season string (e.g. "2023-24").
    stints_df : pd.DataFrame
        Rotation stints filtered to this season.
    pbp_bronze_dir : Path
        Base directory for bronze PBP files.
    max_games : int, optional
        Limit games for testing.

    Returns
    -------
    pd.DataFrame with linked events.
    """
    pbp_dir = pbp_bronze_dir / season / "games"
    if not pbp_dir.exists():
        print(f"  No PBP dir for {season}")
        return pd.DataFrame()

    pbp_files = sorted(pbp_dir.glob("*.json.gz"))
    if max_games:
        pbp_files = pbp_files[:max_games]

    game_ids = [f.name.replace(".json.gz", "") for f in pbp_files]
    print(f"  [{season}] {len(game_ids)} games to process")

    # Pre-index stints by game_id for fast lookup
    stints_by_game = {}
    for gid, grp in stints_df.groupby("GAME_ID"):
        stints_by_game[gid] = grp

    all_linked = []
    errors = 0

    for i, game_id in enumerate(game_ids):
        if i % 200 == 0 and i > 0:
            print(f"  [{season}] {i}/{len(game_ids)} games...")

        game_stints = stints_by_game.get(game_id, pd.DataFrame())
        if len(game_stints) == 0:
            continue

        try:
            pbp_file = pbp_dir / f"{game_id}.json.gz"
            with gzip.open(pbp_file, "rt") as f:
                pbp_data = json.load(f)

            pbp_df = pd.DataFrame(pbp_data["data"])
            pbp_df = _normalize_cdn_taxonomy(pbp_df)
            pbp_df["event_time"] = pbp_df.apply(
                lambda row: parse_clock_to_seconds(row["clock"], row["period"]),
                axis=1,
            )

            linked = link_game_vectorized(pbp_df, game_stints, game_id)
            if len(linked) > 0:
                all_linked.append(linked)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  [{season}] Error on {game_id}: {e}")

    if not all_linked:
        return pd.DataFrame()

    result = pd.concat(all_linked, ignore_index=True)
    # Provenance: stamp the lineup source from the stints used to link this season
    # (gamerotation_exact vs pbp_reconstructed). Reaching this line means games were
    # linked, so stints_df is non-empty and uniform-source per season; STINT_SOURCE
    # is a hard contract (its absence surfaces as KeyError, not a silent default).
    # Propagates to possessions/rapm_stints/event_training_table so reconstruction-
    # linked seasons can never be silently treated as exact.
    result["LINEUP_SOURCE"] = stints_df["STINT_SOURCE"].iloc[0]
    valid_pct = result["lineup_valid"].mean()
    print(f"  [{season}] Linked: {len(result):,} events, {valid_pct:.1%} valid, "
          f"{errors} errors, source={result['LINEUP_SOURCE'].iloc[0]}")
    return result
