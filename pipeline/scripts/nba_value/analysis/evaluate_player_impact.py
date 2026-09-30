"""D5 player-impact evaluation: pregame.v1 candidate vs B0/B1/B2 baselines, two
tracks, frozen 2026-09-26 (RUNDOC "D5 evaluation contract" under
"## 4. KPI, baseline, and stop condition", commit 420003edd).

Two phases share one report file:

  --phase development (seasons 2016-17..2022-23): estimates the frozen
  parameters -- the home-court constant h and the 80% interval residual
  quantiles (10th/90th percentile), per estimator x track -- from development
  games only, and writes the `development` + `frozen_parameters` blocks plus
  `contract_commit` into the report (create).

  --phase holdout (seasons 2023-24, 2024-25): refuses unless the report already
  has a `development` block and `frozen_parameters`. Reuses those frozen
  parameters verbatim (never re-estimated on holdout data), and adds the
  `holdout` block plus the `promotion_decision` (paired game-level bootstrap).
  This script does not decide *when* the holdout may be read -- that operator
  timing decision is outside this file; it only enforces that development
  results already exist.

Estimators (theta, per player; unrated = ridge prior mean 0):
  pregame_v1  betts.rapm.corrected_possessions.pregame.v1, latest issuance
              strictly before the game date.
  B0_home_only  theta == 0 identically (home-court only).
  B1_prev_v2    season S-1 retrospective betts.rapm.corrected_possessions.v2.
  B2_prev_incumbent  season S-1 gold PSF RAPM_NET (legacy LA-RAPM).

Track A (actual participation) uses the game's real stints; Track B (pregame
operational) projects each team's minutes from its last 10 regular-season
games (players who appeared in at least one of the last 3), normalised to 240
per team, and applies theta at that projected rate. Neither track ever uses
the game's own or later minutes for track B.

  reports/nba_value/player_impact_value/d2_evaluation.json, .md

Usage:
  python scripts/nba_value/analysis/evaluate_player_impact.py --phase development \\
      --season-run 2015-16=<v12 dir> --season-run 2016-17=<dir> ... \\
      --pregame-run 2016-17=<dir> ... --v2-fit 2015-16=<dir> ... \\
      --report reports/nba_value/player_impact_value/d2_evaluation.json
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api.src.ml.io.atomic_io import write_json_atomic
from scripts.nba_value.calibration.fit_rapm_corrected import (
    ESTIMATOR_ID as V2_ESTIMATOR_ID,
)
from scripts.nba_value.calibration.fit_rapm_corrected import load_releasable_run
from scripts.nba_value.calibration.fit_rapm_pregame import (
    ESTIMATOR_ID as PREGAME_ESTIMATOR_ID,
)
from scripts.nba_value.calibration.fit_rapm_pregame import prior_season

CONTRACT_COMMIT = "420003edd"
DEVELOPMENT_SEASONS = ["2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
HOLDOUT_SEASONS = ["2023-24", "2024-25"]
ESTIMATORS = ("pregame_v1", "B0_home_only", "B1_prev_v2", "B2_prev_incumbent")
TRACKS = ("track_a", "track_b")
REGULAR_SEASON_PREFIX = "002"
LINEUP_SIZE = 5
LAST_N_GAMES = 10
AVAILABILITY_N_GAMES = 3
TEAM_MINUTES_TOTAL = 240.0
DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"


def _zfill(s: pd.Series) -> pd.Series:
    return s.astype(str).str.zfill(10)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_season_run(run_dir: Path, tg_reg: pd.DataFrame):
    """A releasable v12 season run's stints plus a per-game summary: the
    evaluation target (100 x combined net points / combined possession rows),
    home/away team ids (cross-checked against possessions' OFFENSE_TEAM_ID),
    and GAME_DATE. Reuses `load_releasable_run` for the releasability gate.

    A small number of admitted games (present in possessions.parquet) carry
    zero retained stints -- every segment failed lineup validity, so there is
    no player-level information at all, not merely a disagreement. Those games
    cannot be scored by any estimator on either track and are excluded here,
    counted in the returned `data_gaps`, for the report to disclose -- never
    silently, and never by guessing a home/away identity that does not exist."""
    stints, manifest = load_releasable_run(Path(run_dir))
    poss = pd.read_parquet(Path(run_dir) / "possessions.parquet",
                          columns=["GAME_ID", "OFFENSE_TEAM_ID", "HOME_PTS", "AWAY_PTS"])
    stints = stints.assign(game_id=_zfill(stints["game_id"]))
    poss = poss.assign(GAME_ID=_zfill(poss["GAME_ID"]))

    nunique = stints.groupby("game_id")[["home_team_id", "away_team_id"]].nunique()
    if (nunique != 1).to_numpy().any():
        bad = nunique[(nunique != 1).any(axis=1)].index.tolist()[:5]
        raise ValueError(f"{run_dir}: inconsistent home/away team id within a game: {bad}")
    home_away = stints.groupby("game_id")[["home_team_id", "away_team_id"]].first()

    poss_summary = poss.groupby("GAME_ID").agg(N_POSS_ROWS=("HOME_PTS", "size"), HOME_PTS=("HOME_PTS", "sum"),
                                              AWAY_PTS=("AWAY_PTS", "sum"))
    poss_summary["ACTUAL"] = 100.0 * (poss_summary["HOME_PTS"] - poss_summary["AWAY_PTS"]) / poss_summary["N_POSS_ROWS"]

    no_stints = sorted(set(poss_summary.index) - set(home_away.index))
    if no_stints:
        poss_summary = poss_summary.drop(index=no_stints)

    offense_by_game = poss.groupby("GAME_ID")["OFFENSE_TEAM_ID"].apply(lambda s: {int(x) for x in s.dropna()})
    expected = {gid: {int(r["home_team_id"]), int(r["away_team_id"])} for gid, r in home_away.iterrows()}
    mismatched = [g for g in poss_summary.index if not offense_by_game.get(g, set()) <= expected[g]]
    if mismatched:
        raise ValueError(f"{run_dir}: possessions OFFENSE_TEAM_ID disagrees with stints home/away "
                         f"team ids for games {mismatched[:5]}")

    poss_summary = poss_summary.join(home_away)
    if poss_summary[["home_team_id", "away_team_id"]].isna().to_numpy().any():
        raise ValueError(f"{run_dir}: stints and possessions cover different game sets")

    dates = tg_reg.drop_duplicates("GAME_ID").set_index("GAME_ID")["GAME_DATE"]
    poss_summary["GAME_DATE"] = poss_summary.index.map(dates)
    missing = poss_summary[poss_summary["GAME_DATE"].isna()].index.tolist()
    if missing:
        raise ValueError(f"{run_dir}: {len(missing)} admitted game(s) missing GAME_DATE: {missing[:5]}")
    data_gaps = {"games_excluded_no_stints": no_stints}
    return stints, poss_summary, manifest, data_gaps


def load_v2_theta(v2_fit_dir: Path, expected_season: str) -> dict:
    """B1: season `expected_season`'s retrospective v2 fit, PLAYER_ID -> RAPM_NET."""
    manifest = json.loads((Path(v2_fit_dir) / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("estimator_id") != V2_ESTIMATOR_ID or manifest.get("target_season") != expected_season:
        raise ValueError(f"{v2_fit_dir}: expected a {V2_ESTIMATOR_ID!r} fit for {expected_season!r}, got "
                         f"estimator_id={manifest.get('estimator_id')!r} "
                         f"target_season={manifest.get('target_season')!r}")
    df = pd.read_parquet(Path(v2_fit_dir) / "rapm_v2.parquet", columns=["PLAYER_ID", "RAPM_NET"])
    return {int(pid): float(v) for pid, v in zip(df["PLAYER_ID"], df["RAPM_NET"])}


def load_gold_theta(psf: pd.DataFrame, season: str) -> dict:
    """B2: gold PSF RAPM_NET (legacy LA-RAPM) for `season`. PLAYER_ID is object
    dtype in PSF -- cast explicitly rather than trusting it's already numeric."""
    rows = psf[(psf["SEASON_ID"] == season) & psf["RAPM_NET"].notna()]
    pids = pd.to_numeric(rows["PLAYER_ID"], errors="raise").astype("int64")
    return {int(pid): float(v) for pid, v in zip(pids, rows["RAPM_NET"])}


def load_pregame_run(pregame_dir: Path, expected_season: str) -> pd.DataFrame:
    manifest = json.loads((Path(pregame_dir) / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("estimator_id") != PREGAME_ESTIMATOR_ID or manifest.get("target_season") != expected_season:
        raise ValueError(f"{pregame_dir}: expected a {PREGAME_ESTIMATOR_ID!r} run for {expected_season!r}, "
                         f"got estimator_id={manifest.get('estimator_id')!r} "
                         f"target_season={manifest.get('target_season')!r}")
    return pd.read_parquet(Path(pregame_dir) / "rapm_pregame.parquet")


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def assign_issuance(game_dates: pd.Series, issuance_dates) -> pd.Series:
    """For each GAME_ID (index of `game_dates`), the latest issuance date
    strictly before the game date -- NaT if none (the season's first date)."""
    issuance_dates = sorted(pd.to_datetime(pd.Index(issuance_dates).unique()))
    left = pd.DataFrame({"game_id": game_dates.index, "GAME_DATE": pd.to_datetime(game_dates.to_numpy())})
    left = left.sort_values("GAME_DATE")
    right = pd.DataFrame({"ISSUED_AT": issuance_dates}).sort_values("ISSUED_AT")
    asof = pd.merge_asof(left, right, left_on="GAME_DATE", right_on="ISSUED_AT",
                         direction="backward", allow_exact_matches=False)
    return asof.set_index("game_id")["ISSUED_AT"].reindex(game_dates.index)


def _lineup_sum(lineup_col: pd.Series, theta: dict) -> np.ndarray:
    return np.array([sum(theta.get(int(p), 0.0) for p in lineup) for lineup in lineup_col], dtype=float)


def _lineup_membership_count(lineup_col: pd.Series, member_container) -> np.ndarray:
    return np.array([sum(1 for p in lineup if int(p) in member_container) for lineup in lineup_col], dtype=float)


def flag_team_change(pairs: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    """`pairs`: GAME_ID, PLAYER_ID, GAME_DATE, CURRENT_TEAM. `hist`: PLAYER_ID,
    GAME_DATE, TEAM_ID sorted by GAME_DATE (every regular-season game a player
    appeared in). CHANGED is True where the player's most recent regular-season
    game strictly before GAME_DATE exists and was for a different team -- a
    player with no such game (a true debut) is never flagged."""
    if pairs.empty:
        return pairs.assign(TEAM_ID=pd.Series(dtype="int64"), CHANGED=pd.Series(dtype=bool))
    left = pairs.sort_values("GAME_DATE").reset_index(drop=True)
    merged = pd.merge_asof(left, hist, on="GAME_DATE", by="PLAYER_ID", direction="backward",
                          allow_exact_matches=False)
    merged["CHANGED"] = merged["TEAM_ID"].notna() & (merged["TEAM_ID"] != merged["CURRENT_TEAM"])
    return merged


def build_team_schedule(tg_reg: pd.DataFrame) -> dict:
    """TEAM_ID -> (sorted GAME_DATE array, parallel GAME_ID array), regular season."""
    sched = {}
    for team_id, g in tg_reg.sort_values("GAME_DATE").groupby("TEAM_ID"):
        sched[int(team_id)] = (g["GAME_DATE"].to_numpy(), g["GAME_ID"].to_numpy())
    return sched


def build_team_game_players(pgf_reg: pd.DataFrame) -> dict:
    """(TEAM_ID, GAME_ID) -> [(PLAYER_ID, MIN), ...], regular season."""
    out = {}
    for (team_id, game_id), g in pgf_reg.groupby(["TEAM_ID", "GAME_ID"]):
        out[(int(team_id), game_id)] = list(zip(g["PLAYER_ID"].astype("int64"), g["MIN"].astype(float)))
    return out


def project_team_minutes(team_id: int, as_of_date, team_sched: dict, pgf_by_team_game: dict,
                         window: int = LAST_N_GAMES, avail_window: int = AVAILABILITY_N_GAMES):
    """Track B's minutes projection for `team_id` as of `as_of_date` (never using
    a game on or after that date). None if the team has no prior regular-season
    game. Otherwise a PLAYER_ID -> minutes dict normalised to sum to 240,
    restricted to players who appeared in at least one of the team's previous
    `avail_window` games, using each eligible player's mean MIN over the games
    he actually played among the last `window`."""
    dates, game_ids = team_sched.get(int(team_id), (np.array([]), np.array([])))
    idx = int(np.searchsorted(dates, np.datetime64(pd.Timestamp(as_of_date)), side="left"))
    window_ids = game_ids[max(0, idx - window):idx]
    if len(window_ids) == 0:
        return None
    avail_ids = set(window_ids[-avail_window:])

    raw, counts, avail_players = {}, {}, set()
    for gid in window_ids:
        for pid, minutes in pgf_by_team_game.get((int(team_id), gid), []):
            raw[pid] = raw.get(pid, 0.0) + minutes
            counts[pid] = counts.get(pid, 0) + 1
            if gid in avail_ids:
                avail_players.add(pid)
    m_hat_raw = {pid: raw[pid] / counts[pid] for pid in raw if pid in avail_players}
    total = sum(m_hat_raw.values())
    if total <= 0:
        raise ValueError(f"team {team_id} as of {as_of_date}: {len(window_ids)} prior game(s) but zero "
                         f"eligible projected minutes -- unexpected data gap, not a genuine absence")
    scale = TEAM_MINUTES_TOTAL / total
    return {pid: m * scale for pid, m in m_hat_raw.items()}


# --------------------------------------------------------------------------
# Track A: actual participation
# --------------------------------------------------------------------------

def _check_lineup_sizes(stints: pd.DataFrame) -> None:
    bad = stints[(stints["home_lineup"].map(len) != LINEUP_SIZE) | (stints["away_lineup"].map(len) != LINEUP_SIZE)]
    if len(bad):
        raise ValueError(f"non-{LINEUP_SIZE}-man lineup in game(s) {sorted(bad['game_id'].unique())[:5]}")


def track_a_estimator(stints: pd.DataFrame, weight: pd.Series, theta: dict, *, always_rated: bool = False):
    """Per-game player_part = sum_stints weight*(home_theta - away_theta), and
    rated_share = the weight-share of on-court possessions where a player has an
    explicit rating (always 1.0 for B0, whose theta==0 is the whole model, not a
    fallback for missing data)."""
    home_sum = _lineup_sum(stints["home_lineup"], theta)
    away_sum = _lineup_sum(stints["away_lineup"], theta)
    diff = (home_sum - away_sum) * weight.to_numpy()
    player_part = pd.Series(diff, index=stints.index).groupby(stints["game_id"]).sum()
    if always_rated:
        rated_share = pd.Series(1.0, index=player_part.index)
    else:
        home_rated = _lineup_membership_count(stints["home_lineup"], theta.keys())
        away_rated = _lineup_membership_count(stints["away_lineup"], theta.keys())
        rated_frac = (home_rated + away_rated) / (2 * LINEUP_SIZE)
        rated_share = (pd.Series(rated_frac * weight.to_numpy(), index=stints.index)
                      .groupby(stints["game_id"]).sum())
    return player_part, rated_share


def track_a_candidate(stints: pd.DataFrame, weight: pd.Series, pregame_df: pd.DataFrame, game_dates: pd.Series):
    bucket_by_game = assign_issuance(game_dates, pregame_df["ISSUED_AT"])
    player_part = pd.Series(np.nan, index=game_dates.index, dtype=float)
    rated_share = pd.Series(np.nan, index=game_dates.index, dtype=float)
    for bucket in bucket_by_game.dropna().unique():
        games = bucket_by_game[bucket_by_game == bucket].index
        theta = pregame_df.loc[pregame_df["ISSUED_AT"] == bucket].set_index("PLAYER_ID")["RAPM_NET"].to_dict()
        mask = stints["game_id"].isin(games)
        pp, rs = track_a_estimator(stints[mask], weight[mask], theta)
        player_part.loc[pp.index] = pp.to_numpy()
        rated_share.loc[rs.index] = rs.to_numpy()
    return player_part, rated_share, bucket_by_game.notna()


def _explode_track_a_pairs(stints: pd.DataFrame, poss_summary: pd.DataFrame) -> pd.DataFrame:
    home = stints[["game_id", "home_lineup", "home_team_id"]].rename(
        columns={"home_lineup": "lineup", "home_team_id": "team"})
    away = stints[["game_id", "away_lineup", "away_team_id"]].rename(
        columns={"away_lineup": "lineup", "away_team_id": "team"})
    both = pd.concat([home, away], ignore_index=True).explode("lineup").dropna(subset=["lineup"])
    both = both.assign(PLAYER_ID=both["lineup"].astype("int64")).drop_duplicates(subset=["game_id", "PLAYER_ID"])
    both["GAME_DATE"] = both["game_id"].map(poss_summary["GAME_DATE"])
    return both.rename(columns={"game_id": "GAME_ID", "team": "CURRENT_TEAM"})[
        ["GAME_ID", "PLAYER_ID", "GAME_DATE", "CURRENT_TEAM"]]


def build_track_a(season: str, stints: pd.DataFrame, poss_summary: pd.DataFrame, pregame_df: pd.DataFrame,
                  v2_theta: dict, gold_theta: dict, veteran_players: set, pgf_hist: pd.DataFrame) -> pd.DataFrame:
    stints = stints.assign(game_id=_zfill(stints["game_id"]))
    _check_lineup_sizes(stints)
    game_ids = poss_summary.index
    total_poss = stints.groupby("game_id")["possessions"].transform("sum")
    weight = stints["possessions"] / total_poss

    frame = pd.DataFrame(index=game_ids)
    frame["SEASON"] = season
    frame["ACTUAL"] = poss_summary["ACTUAL"]
    frame["GAME_DATE"] = poss_summary["GAME_DATE"]
    frame["WEIGHT"] = stints.groupby("game_id")["possessions"].sum().reindex(game_ids)

    home_vet = _lineup_membership_count(stints["home_lineup"], veteran_players)
    away_vet = _lineup_membership_count(stints["away_lineup"], veteran_players)
    rookie_frac = (2 * LINEUP_SIZE - home_vet - away_vet) / (2 * LINEUP_SIZE)
    frame["ROOKIE_SHARE"] = (pd.Series(rookie_frac * weight.to_numpy(), index=stints.index)
                            .groupby(stints["game_id"]).sum().reindex(game_ids))

    static = {"B0_home_only": ({}, True), "B1_prev_v2": (v2_theta, False), "B2_prev_incumbent": (gold_theta, False)}
    for name, (theta, always_rated) in static.items():
        pp, rs = track_a_estimator(stints, weight, theta, always_rated=always_rated)
        frame[f"PLAYER_PART_{name}"] = pp.reindex(game_ids)
        frame[f"RATED_SHARE_{name}"] = rs.reindex(game_ids)

    pp_c, rs_c, matched_c = track_a_candidate(stints, weight, pregame_df, poss_summary["GAME_DATE"])
    frame["PLAYER_PART_pregame_v1"] = pp_c.reindex(game_ids)
    frame["RATED_SHARE_pregame_v1"] = rs_c.reindex(game_ids)
    frame["MATCHED"] = matched_c.reindex(game_ids, fill_value=False)

    pairs = _explode_track_a_pairs(stints, poss_summary)
    if len(pairs):
        flagged = flag_team_change(pairs, pgf_hist)
        by_game = flagged.groupby("GAME_ID")["CHANGED"].any()
    else:
        by_game = pd.Series(dtype=bool)
    frame["TEAM_CHANGE"] = by_game.reindex(game_ids, fill_value=False)
    return frame


# --------------------------------------------------------------------------
# Track B: pregame operational
# --------------------------------------------------------------------------

def build_track_b(season: str, poss_summary: pd.DataFrame, pregame_df: pd.DataFrame, v2_theta: dict,
                  gold_theta: dict, veteran_players: set, team_sched: dict, pgf_by_team_game: dict,
                  pgf_hist: pd.DataFrame) -> pd.DataFrame:
    game_ids = poss_summary.index
    projections = {}
    for gid, row in poss_summary.iterrows():
        home_mhat = project_team_minutes(row["home_team_id"], row["GAME_DATE"], team_sched, pgf_by_team_game)
        away_mhat = project_team_minutes(row["away_team_id"], row["GAME_DATE"], team_sched, pgf_by_team_game)
        projections[gid] = None if (home_mhat is None or away_mhat is None) else (home_mhat, away_mhat)
    matched_proj = pd.Series({g: projections[g] is not None for g in game_ids})
    matched_games = [g for g in game_ids if matched_proj[g]]

    frame = pd.DataFrame(index=game_ids)
    frame["SEASON"] = season
    frame["ACTUAL"] = poss_summary["ACTUAL"]
    frame["GAME_DATE"] = poss_summary["GAME_DATE"]
    frame["WEIGHT"] = 2 * TEAM_MINUTES_TOTAL

    def estimator_cols(theta, always_rated=False):
        pp = pd.Series(np.nan, index=game_ids, dtype=float)
        rs = pd.Series(np.nan, index=game_ids, dtype=float)
        for gid in matched_games:
            home_mhat, away_mhat = projections[gid]
            home_sum = sum(theta.get(p, 0.0) * m / 48.0 for p, m in home_mhat.items())
            away_sum = sum(theta.get(p, 0.0) * m / 48.0 for p, m in away_mhat.items())
            pp.loc[gid] = home_sum - away_sum
            if always_rated:
                rs.loc[gid] = 1.0
            else:
                rated_min = (sum(m for p, m in home_mhat.items() if p in theta) +
                            sum(m for p, m in away_mhat.items() if p in theta))
                rs.loc[gid] = rated_min / (2 * TEAM_MINUTES_TOTAL)
        return pp, rs

    for name, (theta, always_rated) in {"B0_home_only": ({}, True), "B1_prev_v2": (v2_theta, False),
                                        "B2_prev_incumbent": (gold_theta, False)}.items():
        pp, rs = estimator_cols(theta, always_rated)
        frame[f"PLAYER_PART_{name}"] = pp
        frame[f"RATED_SHARE_{name}"] = rs

    game_dates_matched = pd.Series({g: poss_summary.loc[g, "GAME_DATE"] for g in matched_games})
    bucket_by_game = (assign_issuance(game_dates_matched, pregame_df["ISSUED_AT"])
                      if matched_games else pd.Series(dtype="datetime64[ns]"))
    pp_c = pd.Series(np.nan, index=game_ids, dtype=float)
    rs_c = pd.Series(np.nan, index=game_ids, dtype=float)
    for bucket in bucket_by_game.dropna().unique():
        theta = pregame_df.loc[pregame_df["ISSUED_AT"] == bucket].set_index("PLAYER_ID")["RAPM_NET"].to_dict()
        for gid in bucket_by_game[bucket_by_game == bucket].index:
            home_mhat, away_mhat = projections[gid]
            home_sum = sum(theta.get(p, 0.0) * m / 48.0 for p, m in home_mhat.items())
            away_sum = sum(theta.get(p, 0.0) * m / 48.0 for p, m in away_mhat.items())
            pp_c.loc[gid] = home_sum - away_sum
            rated_min = (sum(m for p, m in home_mhat.items() if p in theta) +
                        sum(m for p, m in away_mhat.items() if p in theta))
            rs_c.loc[gid] = rated_min / (2 * TEAM_MINUTES_TOTAL)
    frame["PLAYER_PART_pregame_v1"] = pp_c
    frame["RATED_SHARE_pregame_v1"] = rs_c
    frame["MATCHED"] = matched_proj & bucket_by_game.reindex(game_ids).notna()

    rookie_share = pd.Series(np.nan, index=game_ids, dtype=float)
    pair_rows = []
    for gid in matched_games:
        home_mhat, away_mhat = projections[gid]
        rookie_min = (sum(m for p, m in home_mhat.items() if p not in veteran_players) +
                     sum(m for p, m in away_mhat.items() if p not in veteran_players))
        rookie_share.loc[gid] = rookie_min / (2 * TEAM_MINUTES_TOTAL)
        d = poss_summary.loc[gid, "GAME_DATE"]
        home_team, away_team = int(poss_summary.loc[gid, "home_team_id"]), int(poss_summary.loc[gid, "away_team_id"])
        pair_rows += [(gid, p, d, home_team) for p in home_mhat] + [(gid, p, d, away_team) for p in away_mhat]
    frame["ROOKIE_SHARE"] = rookie_share

    if pair_rows:
        pairs = pd.DataFrame(pair_rows, columns=["GAME_ID", "PLAYER_ID", "GAME_DATE", "CURRENT_TEAM"])
        by_game = flag_team_change(pairs, pgf_hist).groupby("GAME_ID")["CHANGED"].any()
    else:
        by_game = pd.Series(dtype=bool)
    frame["TEAM_CHANGE"] = by_game.reindex(game_ids, fill_value=False)
    return frame


# --------------------------------------------------------------------------
# Cohorts
# --------------------------------------------------------------------------

def attach_early_season(frame: pd.DataFrame) -> pd.DataFrame:
    """The first 20% of each season's admitted games by date (the whole admitted
    population, independent of any estimator's matched set)."""
    frame = frame.copy()
    frame["EARLY_SEASON"] = False
    for idx in frame.groupby("SEASON").groups.values():
        sub = frame.loc[idx].sort_values("GAME_DATE")
        n_early = int(np.ceil(len(sub) * 0.20))
        frame.loc[sub.index[:n_early], "EARLY_SEASON"] = True
    return frame


def attach_rookie_heavy(frame: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Above-median rookie-possession/rookie-minutes share, median taken over
    this phase's pooled matched games for this track (the population actually
    scored)."""
    frame = frame.copy()
    matched = frame[frame["MATCHED"]]
    median_share = float(matched["ROOKIE_SHARE"].median()) if len(matched) else float("nan")
    frame["ROOKIE_HEAVY"] = frame["ROOKIE_SHARE"] > median_share
    return frame, median_share


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def compute_metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    actual, pred = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    resid = actual - pred
    rmse, mae = float(np.sqrt(np.mean(resid ** 2))), float(np.mean(np.abs(resid)))
    if len(actual) > 1 and np.std(pred) > 0:
        r = float(np.corrcoef(pred, actual)[0, 1])
        slope, intercept = (float(v) for v in np.polyfit(pred, actual, 1))
    else:
        r, slope, intercept = float("nan"), float("nan"), float("nan")
    return {"n_games": len(actual), "rmse": rmse, "mae": mae, "pearson_r": r,
           "calibration_intercept": intercept, "calibration_slope": slope}


def interval_coverage(actual: np.ndarray, pred: np.ndarray, q10: float, q90: float) -> dict:
    actual, pred = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    covered = (actual >= pred + q10) & (actual <= pred + q90)
    return {"coverage": float(covered.mean()) if len(actual) else float("nan"), "mean_width": float(q90 - q10)}


def estimate_frozen_params(dev_frame: pd.DataFrame, estimator: str) -> dict:
    """h (development-only mean residual, slope fixed at 1) and the 10th/90th
    percentile of the residuals around that h -- development games only,
    frozen for reuse in the holdout phase."""
    matched = dev_frame[dev_frame["MATCHED"]]
    if len(matched) == 0:
        raise ValueError(f"no matched development games for estimator {estimator!r}")
    resid0 = matched["ACTUAL"] - matched[f"PLAYER_PART_{estimator}"]
    h = float(resid0.mean())
    q10, q90 = (float(v) for v in np.percentile((resid0 - h).to_numpy(), [10, 90]))
    return {"h": h, "q10": q10, "q90": q90, "n_development_games": len(matched)}


def estimator_metrics(frame: pd.DataFrame, estimator: str, frozen: dict):
    if len(frame) == 0:
        return None
    pred = frame[f"PLAYER_PART_{estimator}"] + frozen[estimator]["h"]
    m = compute_metrics(frame["ACTUAL"].to_numpy(), pred.to_numpy())
    cov = interval_coverage(frame["ACTUAL"].to_numpy(), pred.to_numpy(), frozen[estimator]["q10"],
                           frozen[estimator]["q90"])
    weight, rated = frame["WEIGHT"].to_numpy(), frame[f"RATED_SHARE_{estimator}"].to_numpy()
    rating_coverage_pct = float(np.sum(rated * weight) / np.sum(weight)) if weight.sum() else float("nan")
    return {**m, "interval_coverage": cov["coverage"], "interval_mean_width": cov["mean_width"],
           "rating_coverage_pct": rating_coverage_pct}


def track_metrics_block(frame: pd.DataFrame, frozen_track: dict, rookie_median: float) -> dict:
    matched = frame[frame["MATCHED"]]
    seasons = sorted(matched["SEASON"].unique())
    metrics = {"pooled": {est: estimator_metrics(matched, est, frozen_track) for est in ESTIMATORS}}
    for s in seasons:
        metrics[s] = {est: estimator_metrics(matched[matched["SEASON"] == s], est, frozen_track)
                     for est in ESTIMATORS}
    matched_games = {"pooled": len(matched)}
    for s in seasons:
        matched_games[s] = int((matched["SEASON"] == s).sum())

    cohorts = {}
    for name, mask in [("rookie_heavy", matched["ROOKIE_HEAVY"]), ("early_season", matched["EARLY_SEASON"]),
                       ("team_change", matched["TEAM_CHANGE"])]:
        sub = matched[mask]
        entry = {"n_games": len(sub), "pooled": {est: estimator_metrics(sub, est, frozen_track)
                                                       for est in ESTIMATORS}}
        if name == "rookie_heavy":
            entry["median_share"] = rookie_median
        cohorts[name] = entry
    return {"matched_games": matched_games, "metrics": metrics, "cohorts": cohorts}


def bootstrap_rmse_diff(actual, pred_candidate, pred_baseline, n_resamples: int, seed: int) -> dict:
    """Paired game-level bootstrap of RMSE(candidate) - RMSE(baseline): resample
    matched games (with replacement), recompute both RMSEs on the same resample,
    repeat `n_resamples` times under a fixed seed (deterministic)."""
    actual = np.asarray(actual, dtype=float)
    pred_candidate = np.asarray(pred_candidate, dtype=float)
    pred_baseline = np.asarray(pred_baseline, dtype=float)
    n = len(actual)
    if n == 0:
        raise ValueError("bootstrap requires at least one matched game")
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_resamples, dtype=float)
    for b in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        rmse_c = np.sqrt(np.mean((actual[idx] - pred_candidate[idx]) ** 2))
        rmse_b = np.sqrt(np.mean((actual[idx] - pred_baseline[idx]) ** 2))
        diffs[b] = rmse_c - rmse_b
    lo, hi = (float(v) for v in np.percentile(diffs, [2.5, 97.5]))
    return {"ci_low": lo, "ci_high": hi, "mean_diff": float(diffs.mean()), "n_resamples": n_resamples, "seed": seed}


def build_promotion_decision(frame_a: pd.DataFrame, frame_b: pd.DataFrame, frozen: dict, n_resamples: int,
                             seed: int) -> dict:
    baselines = ["B0_home_only", "B1_prev_v2", "B2_prev_incumbent"]
    result = {"bootstrap": {}, "criterion": "candidate RMSE beats every baseline in both tracks: the 95% "
                                            "CI of RMSE(candidate)-RMSE(baseline) lies entirely below 0"}
    accepted = True
    for track_name, frame in [("track_a", frame_a), ("track_b", frame_b)]:
        matched = frame[frame["MATCHED"]]
        actual = matched["ACTUAL"].to_numpy()
        pred_c = (matched["PLAYER_PART_pregame_v1"] + frozen[track_name]["pregame_v1"]["h"]).to_numpy()
        result["bootstrap"][track_name] = {}
        for baseline in baselines:
            pred_b = (matched[f"PLAYER_PART_{baseline}"] + frozen[track_name][baseline]["h"]).to_numpy()
            ci = bootstrap_rmse_diff(actual, pred_c, pred_b, n_resamples, seed)
            result["bootstrap"][track_name][baseline] = ci
            accepted = accepted and ci["ci_high"] < 0
    result["accepted"] = bool(accepted)
    return result


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def run_evaluation(phase: str, season_runs: dict, pregame_runs: dict, v2_fits: dict, data_root: Path, *,
                  n_resamples: int, seed: int, report_path: Path) -> dict:
    existing = {}
    if Path(report_path).exists():
        existing = json.loads(Path(report_path).read_text(encoding="utf-8"))

    if phase == "development":
        seasons = DEVELOPMENT_SEASONS
    elif phase == "holdout":
        if "development" not in existing or "frozen_parameters" not in existing:
            raise ValueError(f"{report_path}: holdout phase refuses without an existing development "
                             f"block and frozen_parameters -- run --phase development first")
        seasons = HOLDOUT_SEASONS
    else:
        raise ValueError(f"unknown phase {phase!r}")

    psf = pd.read_parquet(data_root / "gold" / "features" / "player_season_features.parquet",
                         columns=["PLAYER_ID", "SEASON_ID", "RAPM_NET"])
    pgf = pd.read_parquet(data_root / "silver" / "nba" / "facts" / "player_game_fact.parquet",
                         columns=["PLAYER_ID", "TEAM_ID", "GAME_ID", "GAME_DATE", "MIN"])
    pgf = pgf.assign(GAME_ID=_zfill(pgf["GAME_ID"]))
    pgf_reg = pgf[pgf["GAME_ID"].str.startswith(REGULAR_SEASON_PREFIX)].copy()
    tg = pd.read_parquet(data_root / "silver" / "nba" / "facts" / "team_game_fact.parquet",
                        columns=["GAME_ID", "TEAM_ID", "GAME_DATE", "SEASON_ID"])
    tg = tg.assign(GAME_ID=_zfill(tg["GAME_ID"]))
    tg_reg = tg[tg["GAME_ID"].str.startswith(REGULAR_SEASON_PREFIX)].copy()

    team_sched = build_team_schedule(tg_reg)
    pgf_by_team_game = build_team_game_players(pgf_reg)
    pgf_hist = pgf_reg[["PLAYER_ID", "GAME_DATE", "TEAM_ID"]].sort_values("GAME_DATE").reset_index(drop=True)

    frame_a_all, frame_b_all = [], []
    data_gaps = {}
    for season in seasons:
        prior = prior_season(season)
        for label, key in (("season", season), ("prior season", prior)):
            if key not in season_runs:
                raise ValueError(f"--season-run missing for {label} {key!r} (evaluating {season})")
        if prior not in v2_fits:
            raise ValueError(f"--v2-fit missing for {prior!r} (needed for B1_prev_v2 of {season})")
        if season not in pregame_runs:
            raise ValueError(f"--pregame-run missing for {season!r}")

        stints, poss_summary, manifest, gaps = load_season_run(Path(season_runs[season]), tg_reg)
        if manifest["season"] != season:
            raise ValueError(f"{season_runs[season]}: run is for {manifest['season']}, not {season}")
        data_gaps[season] = gaps
        prior_stints, _, prior_manifest, _ = load_season_run(Path(season_runs[prior]), tg_reg)
        if prior_manifest["season"] != prior:
            raise ValueError(f"{season_runs[prior]}: run is for {prior_manifest['season']}, not {prior}")
        veteran_players = {int(p) for lineup in
                          pd.concat([prior_stints["home_lineup"], prior_stints["away_lineup"]], ignore_index=True)
                          for p in lineup}

        v2_theta = load_v2_theta(Path(v2_fits[prior]), prior)
        gold_theta = load_gold_theta(psf, prior)
        pregame_df = load_pregame_run(Path(pregame_runs[season]), season)

        frame_a_all.append(build_track_a(season, stints, poss_summary, pregame_df, v2_theta, gold_theta,
                                        veteran_players, pgf_hist))
        frame_b_all.append(build_track_b(season, poss_summary, pregame_df, v2_theta, gold_theta,
                                        veteran_players, team_sched, pgf_by_team_game, pgf_hist))

    frame_a = attach_early_season(pd.concat(frame_a_all))
    frame_b = attach_early_season(pd.concat(frame_b_all))
    frame_a, rookie_median_a = attach_rookie_heavy(frame_a)
    frame_b, rookie_median_b = attach_rookie_heavy(frame_b)

    if phase == "development":
        frozen = {"track_a": {est: estimate_frozen_params(frame_a, est) for est in ESTIMATORS},
                 "track_b": {est: estimate_frozen_params(frame_b, est) for est in ESTIMATORS}}
    else:
        frozen = existing["frozen_parameters"]

    block = {"track_a": track_metrics_block(frame_a, frozen["track_a"], rookie_median_a),
            "track_b": track_metrics_block(frame_b, frozen["track_b"], rookie_median_b)}

    out = dict(existing)
    out["contract_commit"] = CONTRACT_COMMIT
    out.setdefault("created_at_utc", datetime.now(UTC).isoformat())
    out["updated_at_utc"] = datetime.now(UTC).isoformat()
    out["seasons"] = {"development": DEVELOPMENT_SEASONS, "holdout": HOLDOUT_SEASONS}
    out[phase] = block
    out[f"{phase}_seasons_run"] = seasons
    existing_gaps = existing.get("data_gaps", {})
    out["data_gaps"] = {**existing_gaps, **data_gaps}
    if phase == "development":
        out["frozen_parameters"] = frozen
        out["holdout_run"] = out.get("holdout_run", False)
    else:
        out["promotion_decision"] = build_promotion_decision(frame_a, frame_b, frozen, n_resamples, seed)
        out["holdout_run"] = True
    return out


def _phase_markdown(block: dict) -> str:
    rows = ["| Track | Season | Estimator | N | RMSE | MAE | r | Slope | Interval cov | Rating cov |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for track in TRACKS:
        tb = block[track]
        for season, per_est in tb["metrics"].items():
            for est in ESTIMATORS:
                m = per_est.get(est)
                if m is None:
                    continue
                rows.append(f"| {track} | {season} | {est} | {m['n_games']} | {m['rmse']:.3f} | "
                           f"{m['mae']:.3f} | {m['pearson_r']:.3f} | {m['calibration_slope']:.3f} | "
                           f"{m['interval_coverage']:.3f} | {m['rating_coverage_pct']:.3f} |")
    matched = {t: block[t]["matched_games"] for t in TRACKS}
    return "\n".join(rows) + f"\n\nMatched games: {json.dumps(matched)}\n"


def write_markdown(path: Path, result: dict) -> None:
    lines = [f"# D2 player-impact evaluation (contract {result.get('contract_commit')})", ""]
    if "development" in result:
        lines += ["## Development phase (2016-17..2022-23)", "", _phase_markdown(result["development"])]
    if "holdout" in result:
        lines += ["", "## Holdout phase (2023-24, 2024-25)", "", _phase_markdown(result["holdout"]),
                 "", "## Promotion decision", "```json",
                 json.dumps(result.get("promotion_decision", {}), indent=2), "```"]
    else:
        lines += ["", "**The holdout phase was NOT run.** Only development-phase results are in this report."]
    if "frozen_parameters" in result:
        lines += ["", "## Frozen parameters (development-only, frozen for holdout reuse)", "```json",
                 json.dumps(result["frozen_parameters"], indent=2), "```"]
    lines += ["", f"Wall time: {result.get('wall_time_seconds', 'n/a')} s"]
    text = "\n".join(lines) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_report(report_path: Path, result: dict) -> None:
    write_json_atomic(result, Path(report_path), indent=2, default=str)
    write_markdown(Path(report_path).with_suffix(".md"), result)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", required=True, choices=["development", "holdout"])
    ap.add_argument("--season-run", action="append", default=[], metavar="SEASON=DIR")
    ap.add_argument("--pregame-run", action="append", default=[], metavar="SEASON=DIR")
    ap.add_argument("--v2-fit", action="append", default=[], metavar="SEASON=DIR")
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()

    season_runs = dict(kv.split("=", 1) for kv in args.season_run)
    pregame_runs = dict(kv.split("=", 1) for kv in args.pregame_run)
    v2_fits = dict(kv.split("=", 1) for kv in args.v2_fit)

    t0 = time.time()
    result = run_evaluation(args.phase, season_runs, pregame_runs, v2_fits, args.data_root.resolve(),
                            n_resamples=args.bootstrap, seed=args.seed, report_path=args.report)
    result["wall_time_seconds"] = time.time() - t0
    write_report(args.report, result)
    print(f"Wrote {args.phase} evaluation to {args.report} ({result['wall_time_seconds']:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
