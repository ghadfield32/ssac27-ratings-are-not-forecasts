"""D1 — RAPM denominator and exposure-unit audit (player_metrics_impact RUNDOC).

Answers, from the source records rather than from code comments, what one
"possession" in the LA-RAPM stint target actually is, and therefore whether a
RAPM rate multiplied by a season exposure is a coherent point total.

Evidence produced (all read-only; nothing canonical is written):

  1. Season coverage: reconstructed PBP possession rows, points and retained
     stint possessions versus the box score (both teams,
     FGA + 0.44*FTA - OREB + TOV), per regular-season game.
  2. Possession-closing vocabulary: how often each outcome closes a possession
     versus the box events that should close one (made FG, turnover, defensive
     rebound, final free throw), and the raw actionType/subType strings the
     parser receives for rebounds and free throws.
  3. RAPM artifact trace: TOTAL_POSS in la_rapm_multi_season.parquet
     reconstructed from the raw and from the luck-adjusted stint files (pool of
     seasons_back seasons, decay^seasons_ago), to show which stints were fitted.
  4. Game reconciliations: a regulation game, an overtime game, the most
     substitution-heavy game and a traded player's games, each accounted for
     from box score -> PBP rows -> retained stints.
  5. Player exposure (first pooled season): retained stint rows per player
     versus 2*GP*MIN*E_PACE/48 and versus on-court share x box possessions.

Writes reports/nba_value/player_impact_value/d1_rapm_exposure_audit.{json,md}.

Usage:
  python scripts/nba_value/analysis/audit_rapm_exposure_units.py
  python scripts/nba_value/analysis/audit_rapm_exposure_units.py --data-root <.../data> --cache-root <.../cache>
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api.src.ml.features.rapm_pipeline.config import RapmPipelineConfig
from api.src.ml.io.atomic_io import write_json_atomic

DEFAULT_DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "cache"
DEFAULT_OUT_DIR = PROJECT_ROOT / "reports" / "nba_value" / "player_impact_value"
REGULAR_SEASON_PREFIX = "002"
REGULATION_SECONDS = 2880.0
OVERTIME_SECONDS = 300.0
GAME_ACCOUNTING_COLUMNS = ["GAME_ID", "SEASON_ID", "PERIODS", "PBP_PTS_A", "PBP_PTS_B",
                           "BOX_PTS_A", "BOX_PTS_B", "POSS_A", "POSS_B",
                           "UNATTRIBUTED_POSS", "UNATTRIBUTED_PTS"]


def _gid(s: pd.Series) -> pd.Series:
    return s.astype(str).str.zfill(10)


def box_games(data_root: Path) -> pd.DataFrame:
    """One row per regular-season game: both-team points and box possessions."""
    tg = pd.read_parquet(data_root / "silver/nba/facts/team_game_fact.parquet",
                         columns=["GAME_ID", "TEAM_ID", "SEASON_ID", "PTS", "FGA", "FTA",
                                  "OREB", "DREB", "TOV", "FG", "MATCHUP"])
    tg["GAME_ID"] = _gid(tg["GAME_ID"])
    tg = tg[tg["GAME_ID"].str.startswith(REGULAR_SEASON_PREFIX)]
    tg["BOX_POSS"] = tg["FGA"] + 0.44 * tg["FTA"] - tg["OREB"] + tg["TOV"]
    g = tg.groupby("GAME_ID").agg(SEASON_ID=("SEASON_ID", "first"), N_TEAMS=("TEAM_ID", "size"),
                                  BOX_PTS=("PTS", "sum"), BOX_POSS=("BOX_POSS", "sum"),
                                  BOX_FGM=("FG", "sum"), BOX_TOV=("TOV", "sum"),
                                  BOX_DREB=("DREB", "sum"), BOX_FTA=("FTA", "sum"))
    # A game missing one side has no both-team denominator: NaN, never half a game.
    g.loc[g["N_TEAMS"] != 2, ["BOX_PTS", "BOX_POSS"]] = np.nan
    return g


def box_teams(data_root: Path) -> pd.DataFrame:
    """(GAME_ID, TEAM_ID) -> PTS, FTM and whether the team is the real home side
    ("TEAM vs. OPP" is home in NBA matchup strings, "TEAM @ OPP" is away)."""
    tg = pd.read_parquet(data_root / "silver/nba/facts/team_game_fact.parquet",
                         columns=["GAME_ID", "TEAM_ID", "PTS", "FT", "MATCHUP"])
    tg["GAME_ID"] = _gid(tg["GAME_ID"])
    tg["IS_REAL_HOME"] = tg["MATCHUP"].str.contains(" vs. ", regex=False)
    return tg.set_index(["GAME_ID", "TEAM_ID"])[["PTS", "FT", "IS_REAL_HOME"]]


def stint_frame_margins(stints: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Per game: stint margin vs box margin, both in the STINT's home frame (the
    stint 'home' is the first lineup's team, not necessarily the real home side)."""
    g = stints.groupby("game_id").agg(H=("home_team_id", "first"), A=("away_team_id", "first"),
                                      HP=("home_points", "sum"), AP=("away_points", "sum"))
    h = teams.reindex(list(zip(g.index, g["H"]))).set_axis(g.index)
    a = teams.reindex(list(zip(g.index, g["A"]))).set_axis(g.index)
    return pd.DataFrame({
        "STINT_MARGIN": g["HP"] - g["AP"],
        "BOX_MARGIN_STINT_FRAME": h["PTS"] - a["PTS"],
        "BOX_FT_MARGIN_STINT_FRAME": h["FT"] - a["FT"],
        "STINT_HOME_IS_REAL_HOME": h["IS_REAL_HOME"],
    }, index=g.index)


def _lineup_ok(s: pd.Series) -> pd.Series:
    return s.map(lambda x: x is not None and len(x) == 5)


def season_coverage(data_root: Path, seasons: list, box: pd.DataFrame, teams: pd.DataFrame) -> tuple:
    rows, outcome_rows, per_game = [], [], {}
    sup = data_root / "silver/nba/supplements"
    for season in seasons:
        poss_path = sup / "possessions_by_season" / f"{season}.parquet"
        stint_path = sup / "rapm_stints_by_season" / f"{season}.parquet"
        if not poss_path.exists() or not stint_path.exists():
            rows.append({"season": season, "possessions_file": poss_path.exists(),
                         "stints_file": stint_path.exists(), "status": "SOURCE_MISSING"})
            continue
        p = pd.read_parquet(poss_path, columns=["gameId", "offense_lineup", "defense_lineup",
                                                "outcome", "points_scored", "offense_team"])
        p["gameId"] = _gid(p["gameId"])
        p["OK5"] = _lineup_ok(p["offense_lineup"]) & _lineup_ok(p["defense_lineup"])
        g = p.groupby("gameId").agg(ROWS=("OK5", "size"), ROWS_5V5=("OK5", "sum"),
                                    PBP_PTS=("points_scored", "sum"),
                                    OFFENSE_TEAMS=("offense_team", "nunique"))
        st = pd.read_parquet(stint_path, columns=["game_id", "possessions", "home_points", "away_points",
                                                  "home_team_id", "away_team_id"])
        st["game_id"] = _gid(st["game_id"])
        st["PTS"] = st["home_points"] + st["away_points"]
        sg = st.groupby("game_id").agg(STINT_POSS=("possessions", "sum"), STINT_PTS=("PTS", "sum"))
        g = g.join(sg, how="left").join(box, how="left").join(stint_frame_margins(st, teams), how="left")
        m = g.dropna(subset=["STINT_MARGIN", "BOX_MARGIN_STINT_FRAME", "BOX_FT_MARGIN_STINT_FRAME"])
        non_ft = m["BOX_MARGIN_STINT_FRAME"] - m["BOX_FT_MARGIN_STINT_FRAME"]
        per_game[season] = g
        n_box = int((box["SEASON_ID"] == season).sum())
        rows.append({
            "season": season, "status": "MEASURED",
            "box_regular_season_games": n_box, "pbp_games": len(g),
            "games_missing_from_pbp": n_box - int(g.index.isin(box.index).sum()),
            "median_pbp_rows_per_game": float(g["ROWS"].median()),
            "median_box_combined_poss_per_game": float(g["BOX_POSS"].median()),
            "median_rows_over_box_poss": float((g["ROWS"] / g["BOX_POSS"]).median()),
            "median_pbp_points_over_box_points": float((g["PBP_PTS"] / g["BOX_PTS"]).median()),
            "pbp_points_per_row": float(g["PBP_PTS"].sum() / g["ROWS"].sum()),
            "box_points_per_possession": float(g["BOX_PTS"].sum() / g["BOX_POSS"].sum()),
            "median_offense_teams_per_game": float(g["OFFENSE_TEAMS"].median()),
            "share_rows_with_5v5_lineups": float(g["ROWS_5V5"].sum() / g["ROWS"].sum()),
            "median_stint_poss_over_rows": float((g["STINT_POSS"] / g["ROWS"]).median()),
            "median_stint_poss_over_box_poss": float((g["STINT_POSS"] / g["BOX_POSS"]).median()),
            "median_stint_points_over_box_points": float((g["STINT_PTS"] / g["BOX_PTS"]).median()),
            "share_stint_home_is_real_home": float(g["STINT_HOME_IS_REAL_HOME"].astype(float).mean()),
            "corr_stint_margin_vs_box_margin": float(m["STINT_MARGIN"].corr(m["BOX_MARGIN_STINT_FRAME"])),
            "corr_stint_margin_vs_box_non_ft_margin": float(m["STINT_MARGIN"].corr(non_ft)),
        })
        n = len(g)
        oc = p["outcome"].value_counts()
        bx = box[box.index.isin(g.index)]
        outcome_rows.append({
            "season": season,
            "pbp_field_goal_made_per_game": float(oc.get("field_goal_made", 0) / n),
            "pbp_turnover_per_game": float(oc.get("turnover", 0) / n),
            "pbp_defensive_rebound_per_game": float(oc.get("defensive_rebound", 0) / n),
            "pbp_free_throw_made_per_game": float(oc.get("free_throw_made", 0) / n),
            "pbp_end_of_period_per_game": float(oc.get("end_of_period", 0) / n),
            "box_fgm_per_game": float(bx["BOX_FGM"].mean()),
            "box_tov_per_game": float(bx["BOX_TOV"].mean()),
            "box_dreb_per_game": float(bx["BOX_DREB"].mean()),
            "box_fta_per_game": float(bx["BOX_FTA"].mean()),
        })
    return pd.DataFrame(rows), pd.DataFrame(outcome_rows), per_game


def event_vocabulary(data_root: Path, season: str) -> dict:
    """The raw strings the possession parser receives for its closing events."""
    path = data_root / "silver/nba/supplements/linked_events_by_season" / f"{season}.parquet"
    e = pd.read_parquet(path, columns=["gameId", "actionType", "subType", "shotResult"])
    n = e["gameId"].nunique()
    act = e["actionType"].astype(str).str.strip().str.lower()
    out = {"season": season, "games": int(n)}
    for name, key in [("rebound", "rebound"), ("free throw", "free_throw")]:
        sub = e.loc[act == name, "subType"].astype(str)
        out[f"{key}_subtypes_per_game"] = (sub.value_counts() / n).round(3).head(10).to_dict()
        out[f"{key}_subtypes_containing_parser_token"] = int(
            sub.str.contains("Defensive" if key == "rebound" else "Made", case=False).sum())
    ft = e.loc[act == "free throw", "shotResult"].astype(str)
    out["free_throw_shotResult_per_game"] = (ft.value_counts() / n).round(3).to_dict()
    return out


def rapm_total_poss_trace(data_root: Path, cache_root: Path, seasons: list) -> list:
    """Reconstruct TOTAL_POSS = sum over pooled stints containing the player of
    possessions * decay^seasons_ago, from raw and from luck-adjusted stints."""
    cfg = RapmPipelineConfig()
    art = pd.read_parquet(cache_root / "features" / "la_rapm_multi_season.parquet")
    sup = data_root / "silver/nba/supplements"
    ordered = sorted(cfg.available_seasons)
    results = []
    for target in seasons:
        if target not in ordered:
            continue
        t = ordered.index(target)
        pool = ordered[max(0, t - cfg.seasons_back + 1):t + 1]
        truth = art[art["SEASON"] == target].set_index("PLAYER_ID")["TOTAL_POSS"]
        entry = {"target_season": target, "pool": pool, "decay": cfg.decay_factor,
                 "artifact_players": len(truth)}
        for label, sub in [("raw", "rapm_stints_by_season"), ("luck_adjusted", "rapm_stints_la_by_season")]:
            parts, missing = [], []
            for s in pool:
                f = sup / sub / f"{s}.parquet"
                if not f.exists():
                    missing.append(s)
                    continue
                st = pd.read_parquet(f, columns=["home_lineup", "away_lineup", "possessions"])
                w = st["possessions"].astype(float) * cfg.decay_factor ** (t - ordered.index(s))
                lineups = st["home_lineup"].map(list) + st["away_lineup"].map(list)
                parts.append(pd.DataFrame({"PLAYER_ID": lineups, "W": w}).explode("PLAYER_ID"))
            if not parts:
                entry[label] = {"status": "SOURCE_MISSING", "missing_seasons": missing}
                continue
            rec = pd.concat(parts).astype({"PLAYER_ID": "int64"}).groupby("PLAYER_ID")["W"].sum()
            both = pd.concat([truth.rename("ARTIFACT"), rec.rename("REBUILT")], axis=1, join="inner")
            exact = (both["ARTIFACT"] == both["REBUILT"].astype(int)).mean() if len(both) else np.nan
            entry[label] = {"missing_seasons": missing, "players_matched": len(both),
                            "share_total_poss_exact": float(exact)}
        results.append(entry)
    return results


def rapm_refit_check(data_root: Path, cache_root: Path, target: str) -> dict:
    """Refit one target season with the pipeline's own multi-season ridge on raw
    and on luck-adjusted targets; the matching one is what the artifact holds."""
    from api.src.ml.features.rapm_pipeline.la_rapm import fit_multi_season_rapm

    cfg = RapmPipelineConfig()
    ordered = sorted(cfg.available_seasons)
    t = ordered.index(target)
    pool = ordered[max(0, t - cfg.seasons_back + 1):t + 1]
    sup = data_root / "silver/nba/supplements"
    art = (pd.read_parquet(cache_root / "features" / "la_rapm_multi_season.parquet")
           .query("SEASON == @target").set_index("PLAYER_ID")["RAPM_NET"])
    out = {"target_season": target, "pool": pool, "lambda_reg": cfg.lambda_reg,
           "decay": cfg.decay_factor}
    for label, sub in [("raw", "rapm_stints_by_season"), ("luck_adjusted", "rapm_stints_la_by_season")]:
        files = {s: sup / sub / f"{s}.parquet" for s in pool}
        if not all(f.exists() for f in files.values()):
            out[label] = {"status": "SOURCE_MISSING"}
            continue
        stints = {}
        for s, f in files.items():
            st = pd.read_parquet(f)
            if label == "luck_adjusted":
                st["net_rating_per_100"] = st["net_rating_la"]
            stints[s] = st
        fit = fit_multi_season_rapm(stints, target, cfg).set_index("PLAYER_ID")["RAPM_NET"]
        both = pd.concat([art.rename("A"), fit.rename("F")], axis=1, join="inner")
        out[label] = {"players_matched": len(both),
                      "max_abs_diff_vs_artifact": float((both["A"] - both["F"]).abs().max())}
    return out


def game_reconciliations(data_root: Path, season: str, per_game: pd.DataFrame) -> list:
    sup = data_root / "silver/nba/supplements"
    rot = pd.read_parquet(sup / "game_rotation_player_stint.parquet",
                          columns=["GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "SEASON",
                                   "OUT_TIME_REAL", "STINT_SECONDS"])
    rot["GAME_ID"] = _gid(rot["GAME_ID"])
    rot = rot[(rot["SEASON"] == season) & rot["GAME_ID"].str.startswith(REGULAR_SEASON_PREFIX)]
    gsec = rot.groupby("GAME_ID")["OUT_TIME_REAL"].max() / 10.0
    stints_per_game = rot.groupby("GAME_ID").size()
    pg = per_game[per_game.index.isin(gsec.index)].join(gsec.rename("GAME_SECONDS"))

    picks = []
    reg = pg[pg["GAME_SECONDS"] == REGULATION_SECONDS]
    if len(reg):
        picks.append(("regulation", reg.index[len(reg) // 2]))
    ot = pg[pg["GAME_SECONDS"] > REGULATION_SECONDS]
    if len(ot):
        picks.append(("overtime", ot["GAME_SECONDS"].idxmax()))
    sub_heavy = stints_per_game[stints_per_game.index.isin(pg.index)]
    if len(sub_heavy):
        picks.append(("substitution_heavy", sub_heavy.idxmax()))
    teams = rot.groupby("PLAYER_ID")["TEAM_ID"].nunique()
    traded = teams[teams > 1].index
    traded_games = []
    if len(traded):
        pid = int(traded[0])
        pr = rot[rot["PLAYER_ID"] == pid]
        for tid, grp in pr.groupby("TEAM_ID"):
            gid = grp["GAME_ID"].iloc[0]
            if gid in pg.index:
                picks.append((f"traded_player_{pid}_team_{int(tid)}", gid))
                traded_games.append(gid)

    stints = pd.read_parquet(sup / "rapm_stints_by_season" / f"{season}.parquet",
                             columns=["game_id", "home_lineup", "away_lineup", "possessions",
                                      "home_points", "away_points"])
    stints["game_id"] = _gid(stints["game_id"])
    out = []
    for kind, gid in picks:
        r = pg.loc[gid]
        gs = stints[stints["game_id"] == gid]
        entry = {
            "case": kind, "game_id": gid, "game_seconds": float(r["GAME_SECONDS"]),
            "box_points_both": float(r["BOX_PTS"]), "box_possessions_both": float(r["BOX_POSS"]),
            "stint_home_is_real_home": bool(r["STINT_HOME_IS_REAL_HOME"]),
            "box_margin_stint_frame": float(r["BOX_MARGIN_STINT_FRAME"]),
            "box_ft_margin_stint_frame": float(r["BOX_FT_MARGIN_STINT_FRAME"]),
            "pbp_rows": int(r["ROWS"]), "pbp_rows_5v5": int(r["ROWS_5V5"]),
            "pbp_points": float(r["PBP_PTS"]),
            "stints_retained": len(gs), "stint_possessions": float(gs["possessions"].sum()),
            "stint_points": float((gs["home_points"] + gs["away_points"]).sum()),
            "stint_margin_stint_frame": float((gs["home_points"] - gs["away_points"]).sum()),
            "rotation_stints": int(stints_per_game.get(gid, 0)),
        }
        if kind.startswith("traded_player_"):
            pid = int(kind.split("_")[2])
            on_court = (gs["home_lineup"].map(list) + gs["away_lineup"].map(list))
            in_game = on_court.map(lambda lineup, p=pid: p in lineup)
            onc = rot[(rot["GAME_ID"] == gid) & (rot["PLAYER_ID"] == pid)]["STINT_SECONDS"].sum()
            entry.update({"player_id": pid, "player_oncourt_seconds": float(onc),
                          "player_stint_possessions": float(gs.loc[in_game, "possessions"].sum()),
                          "player_oncourt_share_x_box_poss": float(onc / r["GAME_SECONDS"] * r["BOX_POSS"])})
        out.append(entry)
    return out


def player_exposure_comparison(data_root: Path, season: str) -> dict:
    sup = data_root / "silver/nba/supplements"
    st = pd.read_parquet(sup / "rapm_stints_by_season" / f"{season}.parquet",
                         columns=["home_lineup", "away_lineup", "possessions"])
    lineups = st["home_lineup"].map(list) + st["away_lineup"].map(list)
    rows = (pd.DataFrame({"PLAYER_ID": lineups, "POSS": st["possessions"].astype(float)})
            .explode("PLAYER_ID").astype({"PLAYER_ID": "int64"})
            .groupby("PLAYER_ID")["POSS"].sum())
    psf = pd.read_parquet(data_root / "gold/features/player_season_features.parquet",
                          columns=["PLAYER_ID", "SEASON_ID", "GP", "MIN", "E_PACE"])
    psf = psf[psf["SEASON_ID"] == season].copy()
    psf["PLAYER_ID"] = psf["PLAYER_ID"].astype("int64")
    psf["EST_MIN_X_PACE"] = 2.0 * psf["GP"] * psf["MIN"] * psf["E_PACE"] / 48.0
    j = psf.set_index("PLAYER_ID").join(rows.rename("STINT_ROWS"), how="inner")
    ratio = (j["STINT_ROWS"] / j["EST_MIN_X_PACE"]).replace([np.inf, -np.inf], np.nan).dropna()
    return {"season": season, "players": len(j),
            "median_stint_rows_over_est_min_x_pace": float(ratio.median()),
            "p10": float(ratio.quantile(0.10)), "p90": float(ratio.quantile(0.90))}


def game_periods(data_root: Path) -> pd.Series:
    """GAME_ID -> periods played, from the GameRotation feed's game length; a length
    that is not 2880 + 300k seconds is unknown (NaN), never rounded."""
    rot = pd.read_parquet(data_root / "silver/nba/supplements/game_rotation_player_stint.parquet",
                          columns=["GAME_ID", "OUT_TIME_REAL"])
    rot["GAME_ID"] = _gid(rot["GAME_ID"])
    secs = rot.groupby("GAME_ID")["OUT_TIME_REAL"].max() / 10.0
    ot = (secs - REGULATION_SECONDS) / OVERTIME_SECONDS
    legal = (secs >= REGULATION_SECONDS) & np.isclose(ot, np.round(ot))
    return (4 + np.round(ot)).where(legal).rename("PERIODS")


def expected_cohorts(box: pd.DataFrame) -> dict:
    """Season -> regular-season game ids with both teams in the box record: the
    independent cohort a possession artifact must cover."""
    both = box[box["N_TEAMS"] == 2]
    return {s: set(ids) for s, ids in both.groupby("SEASON_ID").groups.items()}


def possession_accounting(poss: pd.DataFrame, teams: pd.DataFrame, periods: pd.Series,
                          season: str) -> pd.DataFrame:
    """Per-game accounting table for a possession artifact (one row per possession
    with gameId, offense_team, scoring_team, points_scored). Points are credited as
    the RAPM stint builder credits them: scoring_team, else offense_team."""
    p = poss[["gameId", "offense_team", "scoring_team", "points_scored"]].copy()
    p["gameId"] = _gid(p["gameId"])
    for col in ("offense_team", "scoring_team"):
        p[col] = pd.to_numeric(p[col], errors="raise").astype("Int64")
    p["CREDIT_TEAM"] = p["scoring_team"].combine_first(p["offense_team"])
    scored = p[p["points_scored"] > 0]
    box_pts = teams["PTS"].reset_index()
    box_pts = box_pts[box_pts["GAME_ID"].isin(p["gameId"].unique())]
    rows = []
    poss_by = p.dropna(subset=["offense_team"]).groupby(["gameId", "offense_team"]).size()
    pts_by = scored.dropna(subset=["CREDIT_TEAM"]).groupby(["gameId", "CREDIT_TEAM"])["points_scored"].sum()
    unattr_poss = p["offense_team"].isna().groupby(p["gameId"]).sum()
    unattr_pts = scored.loc[scored["CREDIT_TEAM"].isna(), "points_scored"].groupby(scored["gameId"]).sum()
    for gid, grp in box_pts.groupby("GAME_ID"):
        if len(grp) != 2:
            continue   # a one-sided box game is outside the expected cohort
        (ta, pa), (tb, pb) = sorted(zip(grp["TEAM_ID"], grp["PTS"]))
        rows.append({"GAME_ID": gid, "SEASON_ID": season, "PERIODS": periods.get(gid, np.nan),
                     "PBP_PTS_A": pts_by.get((gid, ta), 0), "PBP_PTS_B": pts_by.get((gid, tb), 0),
                     "BOX_PTS_A": pa, "BOX_PTS_B": pb,
                     "POSS_A": poss_by.get((gid, ta), 0), "POSS_B": poss_by.get((gid, tb), 0),
                     "UNATTRIBUTED_POSS": int(unattr_poss.get(gid, 0)),
                     "UNATTRIBUTED_PTS": float(unattr_pts.get(gid, 0))})
    return pd.DataFrame(rows, columns=GAME_ACCOUNTING_COLUMNS)


def game_accounting(games: pd.DataFrame) -> pd.DataFrame:
    """Per-game release predicate. Columns in: GAME_ID, SEASON_ID, PERIODS,
    PBP_PTS_A/B (points the possessions credit to each box team), BOX_PTS_A/B,
    POSS_A/B (possessions each team had), UNATTRIBUTED_POSS/PTS.

    A game is valid only when every point is credited to the right team and
    reconciles to the box score, every possession has an offense team, and the
    two possession counts differ by at most the number of periods (possessions
    alternate, and each period's opening possession can go to either side)."""
    g = games.reindex(columns=GAME_ACCOUNTING_COLUMNS) if games.empty else games.copy()
    g["SCORING_RECONCILED"] = (g["PBP_PTS_A"] == g["BOX_PTS_A"]) & (g["PBP_PTS_B"] == g["BOX_PTS_B"])
    g["ATTRIBUTION_COMPLETE"] = (g["UNATTRIBUTED_POSS"] == 0) & (g["UNATTRIBUTED_PTS"] == 0)
    # Unknown period count is unverifiable: the comparison with NaN is False.
    g["ALTERNATION_OK"] = (g["POSS_A"] - g["POSS_B"]).abs() <= g["PERIODS"]
    g["GAME_VALID"] = g["SCORING_RECONCILED"] & g["ATTRIBUTION_COMPLETE"] & g["ALTERNATION_OK"]
    return g


# Only a game whose SOURCE is absent or unusable may be declared out of a release,
# each reason under a versioned policy; a game whose data is present but wrong
# (scoring, attribution, unexplained alternation) never can be.
EXCLUSION_POLICIES = {
    "no_bronze_pbp": "source-absence-v1",
    "link_empty": "source-absence-v1",
    "no_events_in_source": "source-absence-v1",
    # A legacy-feed game whose scoring reconciles exactly but whose event order is
    # contradictory (time vs scorer entry order) is removed whole, never repaired.
    "source_order_unresolvable": "source-order-v1",
    # A game whose scoring reconciles exactly but where an opponent possession is
    # absent from the source is removed whole, never given a synthesized possession.
    "source_possession_unlogged": "source-absence-v2",
}
EXCLUDABLE_REASONS = set(EXCLUSION_POLICIES)


def season_release(acc: pd.DataFrame, expected: dict, exclusions: dict | None = None) -> dict:
    """Per season: every expected game (independent box cohort) present and valid,
    except explicitly declared source-absence exclusions.

    `exclusions`: GAME_ID -> {"declared": reason, "actual": the game's quarantine
    reason}. An exclusion is accepted only if both agree and the reason is in
    EXCLUDABLE_REASONS; any other declaration is rejected and fails the season."""
    exclusions = exclusions or {}
    accepted = {g for g, e in exclusions.items()
                if e["declared"] == e["actual"] and e["declared"] in EXCLUDABLE_REASONS}
    out = {}
    for season, want in sorted(expected.items()):
        want = set(want)
        excluded = want & accepted
        rejected = sorted((want & set(exclusions)) - accepted)
        rows = acc[acc["SEASON_ID"] == season] if len(acc) else acc
        if len(rows):
            rows = rows[~rows["GAME_ID"].isin(excluded)]
        present = set(rows["GAME_ID"]) if len(rows) else set()
        invalid = rows[~rows["GAME_VALID"]] if len(rows) else rows
        missing = sorted(want - excluded - present)
        clean = (not missing and len(invalid) == 0 and want and not (present - want)
                 and not rejected)
        out[season] = {
            "expected_games": len(want), "present_games": len(present & want),
            "missing_games": len(missing), "unexpected_games": len(present - want),
            "excluded_games": len(excluded), "excluded": sorted(excluded),
            "rejected_exclusions": rejected,
            "invalid_games": len(invalid),
            "scoring_unreconciled": int((~rows["SCORING_RECONCILED"]).sum()) if len(rows) else 0,
            "attribution_incomplete": int((~rows["ATTRIBUTION_COMPLETE"]).sum()) if len(rows) else 0,
            "alternation_violations": int((~rows["ALTERNATION_OK"]).sum()) if len(rows) else 0,
            "example_invalid_games": list(invalid["GAME_ID"].head(5)) if len(invalid) else [],
            "example_missing_games": missing[:5],
            # A game outside the independent cohort is unexplained provenance, not a pass.
            "status": ("FAIL" if not clean else "PASS_WITH_EXCLUSIONS" if excluded else "PASS"),
        }
    return out


PASSING_RELEASE = {"PASS", "PASS_WITH_EXCLUSIONS"}


def lineage_record(paths: dict) -> dict:
    """name -> {path, sha256}; a missing file records sha256 None (never current)."""
    rec = {}
    for name, p in paths.items():
        p = Path(p)
        rec[name] = {"path": str(p),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None}
    return rec


def lineage_current(lineage: dict) -> bool:
    """True only if every recorded artifact still exists with the recorded bytes."""
    for entry in lineage.values():
        p = Path(entry["path"])
        if entry["sha256"] is None or not p.exists():
            return False
        if hashlib.sha256(p.read_bytes()).hexdigest() != entry["sha256"]:
            return False
    return True


def exit_code(v: dict, *, enforce: bool) -> int:
    """Writing the report succeeds either way; --enforce makes an unresolved unit a
    non-zero exit so a scheduler cannot treat report generation as a domain pass."""
    return 3 if enforce and v["la_rapm_net_point_unit_status"] != "points" else 0


def verdict(coverage: pd.DataFrame, outcomes: pd.DataFrame, vocab: dict, seasons: dict,
            *, lineage_ok: bool) -> dict:
    """Every flag is derived from the measurements above, never asserted. The unit
    is `points` only when every audited season passes game-level accounting and
    the audit is bound to the exact artifacts it measured."""
    measured = coverage[coverage["status"] == "MEASURED"]
    rows_cov = measured["median_rows_over_box_poss"]
    dreb_closes = float(outcomes["pbp_defensive_rebound_per_game"].sum())
    ft_closes = float(outcomes["pbp_free_throw_made_per_game"].sum())
    failing = sorted(s for s, r in seasons.items() if r["status"] not in PASSING_RELEASE)
    convention_holds = bool(seasons) and not failing and lineage_ok
    # Rows alternate between both teams' possessions -> not a per-team count.
    both_teams = bool((measured["median_offense_teams_per_game"] == 2).all())
    # Share of the rows->box possession gap that the min_poss_per_stint filter causes.
    stint_over_box = measured["median_stint_poss_over_box_poss"]
    filter_share = ((1 - measured["median_stint_poss_over_rows"]) / (1 - stint_over_box)).median()
    return {
        "la_rapm_net_point_unit_status": "points" if convention_holds else "unresolved",
        "rate_unit_as_built": ("net points per 100 combined possessions" if convention_holds
                               else "net points per 100 reconstructed PBP possession rows"),
        "combined_possession_convention_holds": convention_holds,
        "failing_seasons": failing,
        "lineage_current": lineage_ok,
        "seasons": seasons,
        "rows_contain_both_teams_possessions": both_teams,
        "per_team_counting_explains_ratio": not both_teams,
        "share_of_gap_from_min_poss_filter": float(filter_share),
        "min_poss_filter_explains_ratio": bool(filter_share > 0.5),
        "defensive_rebound_closes_observed": dreb_closes,
        "free_throw_closes_observed": ft_closes,
        "parser_token_hits": {"rebound_Defensive": vocab["rebound_subtypes_containing_parser_token"],
                              "free_throw_Made": vocab["free_throw_subtypes_containing_parser_token"]},
        "stint_home_frame_is_real_home_share_range": [
            float(measured["share_stint_home_is_real_home"].min()),
            float(measured["share_stint_home_is_real_home"].max())],
        "rows_over_box_possessions_range": [float(rows_cov.min()), float(rows_cov.max())],
        "stint_possessions_over_box_possessions_range": [float(stint_over_box.min()),
                                                         float(stint_over_box.max())],
        "cause": None if convention_holds else (
            "scripts/nba_value/data/infer_possessions.py closes a possession only on made field "
            "goal, turnover or period end: the V3 event feed labels rebounds subType "
            "'Unknown'/'Normal Rebound' (the parser tests 'Defensive') and free throws "
            "'Free Throw k of n' (the parser tests 'Made'), so defensive-rebound and free-throw "
            "closes never fire and free-throw points are never added."),
        "consequence": None if convention_holds else (
            "One row spans about two real possessions of either team and rows oversample "
            "scoring trips, so no fixed factor (1x or 2x) converts the RAPM rate to a true "
            "per-possession unit. Season point totals are BLOCKED until possessions are "
            "rebuilt and RAPM is refit as a reviewed challenger."),
    }


def fitted_on(refit: dict) -> str:
    """The stint set whose refit reproduces the artifact to numerical precision."""
    diffs = {k: v["max_abs_diff_vs_artifact"] for k, v in refit.items()
             if isinstance(v, dict) and "max_abs_diff_vs_artifact" in v}
    exact = [k for k, d in diffs.items() if d < 1e-6]
    return exact[0] if len(exact) == 1 else f"UNDETERMINED {diffs}"


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--vocab-season", default="2018-19")
    ap.add_argument("--game-season", default="2023-24")
    ap.add_argument("--player-season", default="2015-16")
    ap.add_argument("--refit-season", default="2023-24")
    ap.add_argument("--enforce", action="store_true",
                    help="exit 3 unless the verdict is points (for schedulers)")
    args = ap.parse_args()

    seasons = RapmPipelineConfig().available_seasons
    box = box_games(args.data_root)
    teams = box_teams(args.data_root)
    coverage, outcomes, per_game = season_coverage(args.data_root, seasons, box, teams)
    periods = game_periods(args.data_root)
    sup = args.data_root / "silver/nba/supplements"
    acc_parts, lineage_paths = [], {
        "parser": PROJECT_ROOT / "scripts/nba_value/data/infer_possessions.py",
        "rapm_artifact": args.cache_root / "features" / "la_rapm_multi_season.parquet"}
    for season in seasons:
        f = sup / "possessions_by_season" / f"{season}.parquet"
        if f.exists():
            acc_parts.append(possession_accounting(
                pd.read_parquet(f, columns=["gameId", "offense_team", "scoring_team", "points_scored"]),
                teams, periods, season))
            lineage_paths[f"possessions/{season}"] = f
        stint = sup / "rapm_stints_by_season" / f"{season}.parquet"
        if stint.exists():
            lineage_paths[f"stints/{season}"] = stint
    acc = game_accounting(pd.concat(acc_parts, ignore_index=True))
    cohorts = expected_cohorts(box)
    season_status = season_release(acc, {s: cohorts.get(s, set()) for s in seasons})
    lineage = lineage_record(lineage_paths)
    vocab = event_vocabulary(args.data_root, args.vocab_season)
    trace = rapm_total_poss_trace(args.data_root, args.cache_root, ["2015-16", "2017-18", "2023-24"])
    refit = rapm_refit_check(args.data_root, args.cache_root, args.refit_season)
    games = game_reconciliations(args.data_root, args.game_season, per_game[args.game_season])
    player = player_exposure_comparison(args.data_root, args.player_season)
    report = {
        "audit": "D1 rapm exposure units", "generated_at_utc": datetime.now(UTC).isoformat(),
        "data_root": str(args.data_root), "cache_root": str(args.cache_root),
        "verdict": {**verdict(coverage, outcomes, vocab, season_status,
                              lineage_ok=lineage_current(lineage)),
                    "rapm_net_fitted_on": fitted_on(refit)},
        "lineage": lineage,
        "season_coverage": coverage.to_dict("records"),
        "possession_outcomes_vs_box": outcomes.to_dict("records"),
        "event_vocabulary": vocab, "rapm_total_poss_trace": trace, "rapm_refit_check": refit,
        "game_reconciliations": games, "player_exposure": player,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(report, args.out_dir / "d1_rapm_exposure_audit.json", indent=2)

    measured = coverage[coverage["status"] == "MEASURED"]
    md = [
        "# D1 — RAPM denominator and exposure-unit audit", "",
        f"Generated {report['generated_at_utc']} by `scripts/nba_value/analysis/audit_rapm_exposure_units.py`.", "",
        "## Verdict", "", "```json", json.dumps(report["verdict"], indent=2), "```", "",
        "## Release accounting per season (every expected game must reconcile)", "",
        _md_table(pd.DataFrame([{"season": k, **{c: v[c] for c in (
            "status", "expected_games", "present_games", "missing_games", "unexpected_games", "invalid_games",
            "scoring_unreconciled", "attribution_incomplete", "alternation_violations")}}
            for k, v in season_status.items()])), "",
        "## Season coverage (medians per regular-season game)", "",
        _md_table(measured[["season", "pbp_games", "box_regular_season_games", "median_pbp_rows_per_game",
                            "median_box_combined_poss_per_game", "median_rows_over_box_poss",
                            "median_pbp_points_over_box_points", "pbp_points_per_row",
                            "median_stint_poss_over_rows", "median_stint_poss_over_box_poss"]]), "",
        "## Margin agreement (stint home frame)", "",
        _md_table(measured[["season", "share_stint_home_is_real_home", "corr_stint_margin_vs_box_margin",
                            "corr_stint_margin_vs_box_non_ft_margin"]]), "",
        "## Possession closes per game versus box events", "", _md_table(outcomes), "",
        f"## Parser input vocabulary ({vocab['season']})", "", "```json", json.dumps(vocab, indent=2), "```", "",
        "## RAPM TOTAL_POSS trace", "", "```json", json.dumps(trace, indent=2), "```", "",
        "## RAPM refit check (which stints the artifact was fitted on)", "", "```json",
        json.dumps(refit, indent=2), "```", "",
        f"## Game reconciliations ({args.game_season})", "", _md_table(pd.DataFrame(games).drop(
            columns=[c for c in ["player_id"] if c in pd.DataFrame(games).columns])), "",
        "## Player exposure", "", "```json", json.dumps(player, indent=2), "```", "",
    ]
    (args.out_dir / "d1_rapm_exposure_audit.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: v for k, v in report["verdict"].items() if k != "seasons"}, indent=2))
    print(f"Wrote {args.out_dir / 'd1_rapm_exposure_audit.json'}")
    return exit_code(report["verdict"], enforce=args.enforce)


if __name__ == "__main__":
    raise SystemExit(main())
