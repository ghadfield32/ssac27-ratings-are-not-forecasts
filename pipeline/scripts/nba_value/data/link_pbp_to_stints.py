#!/usr/bin/env python3
"""
Link Play-by-Play events to rotation stints.

For each PBP event, identify which 5-man lineups (home and away) were on court.
This creates the foundation for RAPM analysis.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
import json
import gzip
from datetime import datetime

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

def parse_clock_to_seconds(clock_str: str, period: int) -> float:
    """
    Convert PBP clock to seconds from game start.

    Args:
        clock_str: ISO 8601 duration format (e.g., "PT12M00.00S")
        period: Period number (1-4 for regulation, 5+ for OT)

    Returns:
        float: Seconds from game start
    """
    # Parse ISO 8601 duration: PT12M00.00S -> 12 minutes, 0 seconds
    if not clock_str or clock_str == '':
        return 0.0

    # Remove "PT" prefix
    time_str = clock_str.replace('PT', '')

    # Parse minutes and seconds
    minutes = 0.0
    seconds = 0.0

    if 'M' in time_str:
        parts = time_str.split('M')
        minutes = float(parts[0])
        if 'S' in parts[1]:
            seconds = float(parts[1].replace('S', ''))
    elif 'S' in time_str:
        seconds = float(time_str.replace('S', ''))

    # Time remaining in period (in seconds)
    time_remaining = minutes * 60 + seconds

    # Convert to seconds from game start
    # Regulation periods are 12 minutes (720 seconds)
    # OT periods are 5 minutes (300 seconds)
    if period <= 4:
        # Regulation
        seconds_into_period = 720 - time_remaining
        seconds_from_start = (period - 1) * 720 + seconds_into_period
    else:
        # Overtime
        seconds_into_period = 300 - time_remaining
        seconds_from_start = 4 * 720 + (period - 5) * 300 + seconds_into_period

    return seconds_from_start

def link_events_to_stints(pbp_events: pd.DataFrame, stints: pd.DataFrame, game_id: str) -> pd.DataFrame:
    """
    Link each PBP event to the 5-man lineups (home and away) on court.

    Args:
        pbp_events: DataFrame with PBP events
        stints: DataFrame with rotation stints
        game_id: Game ID

    Returns:
        DataFrame with events + lineup information
    """
    # Filter stints to this game
    game_stints = stints[stints.GAME_ID == game_id].copy()

    if len(game_stints) == 0:
        print(f"  WARNING: No stints found for game {game_id}")
        return pd.DataFrame()

    # Get home/away team IDs
    home_team_id = game_stints[game_stints.TEAM_ID == game_stints.TEAM_ID.mode()[0]]['TEAM_ID'].iloc[0]
    away_team_id = game_stints[game_stints.TEAM_ID != home_team_id]['TEAM_ID'].iloc[0]

    # Convert stint times from tenths of seconds to seconds
    game_stints['IN_TIME_SEC'] = game_stints['IN_TIME_REAL'] / 10.0
    game_stints['OUT_TIME_SEC'] = game_stints['OUT_TIME_REAL'] / 10.0

    # Add lineup info to each event
    events_with_lineups = []

    for idx, event in pbp_events.iterrows():
        event_time = event['event_time']

        # Find home lineup at this time
        home_lineup = game_stints[
            (game_stints.TEAM_ID == home_team_id) &
            (game_stints.IN_TIME_SEC <= event_time) &
            (game_stints.OUT_TIME_SEC > event_time)
        ]['PLAYER_ID'].tolist()

        # Find away lineup at this time
        away_lineup = game_stints[
            (game_stints.TEAM_ID == away_team_id) &
            (game_stints.IN_TIME_SEC <= event_time) &
            (game_stints.OUT_TIME_SEC > event_time)
        ]['PLAYER_ID'].tolist()

        # Check for 5v5 lineup
        if len(home_lineup) == 5 and len(away_lineup) == 5:
            events_with_lineups.append({
                **event.to_dict(),
                'home_lineup': sorted(home_lineup),
                'away_lineup': sorted(away_lineup),
                'lineup_valid': True
            })
        else:
            # Lineup incomplete (substitution in progress, or data issue)
            events_with_lineups.append({
                **event.to_dict(),
                'home_lineup': [],
                'away_lineup': [],
                'lineup_valid': False
            })

    return pd.DataFrame(events_with_lineups)

def process_game(game_id: str, season: str, stints_df: pd.DataFrame) -> pd.DataFrame:
    """
    Process a single game: load PBP, link to stints, return linked events.

    Args:
        game_id: Game ID
        season: Season (e.g., "2024-25")
        stints_df: DataFrame with all stints

    Returns:
        DataFrame with linked events
    """
    # Load PBP from Bronze
    pbp_file = Path(f'data/bronze/nba/play_by_play/{season}/games/{game_id}.json.gz')

    if not pbp_file.exists():
        print(f"  WARNING: PBP file not found: {pbp_file}")
        return pd.DataFrame()

    with gzip.open(pbp_file, 'rt') as f:
        pbp_data = json.load(f)

    # Convert to DataFrame
    pbp_df = pd.DataFrame(pbp_data['data'])

    # Convert clock to seconds from game start
    pbp_df['event_time'] = pbp_df.apply(
        lambda row: parse_clock_to_seconds(row['clock'], row['period']),
        axis=1
    )

    # Link to stints
    linked = link_events_to_stints(pbp_df, stints_df, game_id)

    return linked

def process_season(season: str, max_games: int = None):
    """
    Process all games in a season.

    Args:
        season: Season (e.g., "2024-25")
        max_games: Optional limit on number of games
    """
    print(f"\n{'='*80}")
    print(f"Linking PBP to Stints: {season}")
    print(f"{'='*80}")

    # Load rotation stints from Silver
    stints_df = pd.read_parquet('api/src/airflow_project/data/silver/nba/supplements/game_rotation_player_stint.parquet')
    print(f"Loaded {len(stints_df):,} rotation stints")

    # Get list of games with PBP data
    pbp_dir = Path(f'data/bronze/nba/play_by_play/{season}/games')
    if not pbp_dir.exists():
        print(f"ERROR: No PBP data found for {season}")
        return

    pbp_files = list(pbp_dir.glob('*.json.gz'))
    # Remove both .json and .gz extensions to get clean game IDs
    game_ids = [f.name.replace('.json.gz', '') for f in pbp_files]

    if max_games:
        game_ids = game_ids[:max_games]

    print(f"Games with PBP: {len(game_ids):,}")

    # Process each game
    all_linked = []

    for i, game_id in enumerate(game_ids):
        if i % 5 == 0:
            print(f"[{i}/{len(game_ids)}] Processing {game_id}...")

        linked = process_game(game_id, season, stints_df)

        if len(linked) > 0:
            all_linked.append(linked)

    if len(all_linked) == 0:
        print("ERROR: No linked events")
        return

    # Concatenate all games
    linked_df = pd.concat(all_linked, ignore_index=True)

    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"Total events: {len(linked_df):,}")
    print(f"Valid lineups: {linked_df.lineup_valid.sum():,} ({linked_df.lineup_valid.mean():.1%})")

    # Save to Silver
    output_path = Path('api/src/airflow_project/data/silver/nba/supplements/play_by_play_linked_stints.parquet')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    linked_df.to_parquet(output_path, index=False)

    print(f"\nSaved to {output_path.name}")

    return linked_df

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Link PBP events to rotation stints')
    parser.add_argument('--season', type=str, default='2024-25', help='Season to process')
    parser.add_argument('--max-games', type=int, help='Max games to process (for testing)')

    args = parser.parse_args()

    process_season(args.season, max_games=args.max_games)
