"""PMI D1B — possession ledger CHALLENGER (RUNDOC player_metrics_impact).

Separately versioned reconstruction of scoring, possessions and lineup stints
from the raw play-by-play event feed. It exists because the incumbent parser
(`scripts/nba_value/data/infer_possessions.py`) only closes a possession on a
made field goal, a turnover or a period end -- the V3 feed's rebound subType
is never 'Defensive' and its free-throw subType is never 'Made', so defensive
rebounds and free throws never close a possession, and the events' raw
`home_lineup`/`away_lineup` labels belong to the real home team only ~50% of
the time (see `scripts/nba_value/analysis/audit_rapm_exposure_units.py`).

This module reads no files and writes nothing; every function is a pure
transform over DataFrames the caller supplies.

Pipeline: normalize_events -> scoring_ledger (game-level ADMITTED/QUARANTINED
gate) -> reconstruct_possessions (ADMITTED games only) -> build_stints /
game_accounting_rows.

Convention -- read this before touching the state machine below:

* A possession ends (terminal event) on: a made field goal (unless followed,
  before any other terminal event, by the same team's regular 1-of-1 free
  throw -- an and-one, which becomes the terminal event instead); a turnover;
  a defensive rebound (the rebounding team's id differs from the team of the
  most recent missed field goal or missed FINAL regular free throw); the
  made FINAL regular free throw of a trip; or a period end (closes whatever
  possession is open, even if it is just the period-end event itself).
* A rebound after a missed NON-final regular free throw is a dead-ball event:
  it is consumed but is neither terminal nor a possession change.
* Technical, flagrant and clear-path free throws are NEVER terminal -- the
  fouled team keeps the ball -- but their points are still credited through
  the running scoreboard delta on that event.
* OFFENSE_TEAM_ID of a possession is the team of ITS OWN terminal event: the
  shooter's team for a made shot/free throw, the turnover team, or (for a
  defensive rebound) the team that MISSED -- i.e. the non-rebounding team,
  since a defensive rebound possession is the one that just ended for the
  team that had been shooting. For an end-of-period close it is the team of
  the most recent event in the possession that establishes ball control
  (a made/missed shot, a non-technical free throw, or an offensive rebound);
  <NA> if none occurred.
* SEQ is a per-game 0..n-1 position assigned after a stable sort by
  (PERIOD, ELAPSED, order-column); it doubles as a row's position, so
  START_SEQ/END_SEQ slice directly into the per-game event frame.
* HOME_TEAM_ID/AWAY_TEAM_ID are carried on every normalized row (beyond the
  columns the RUNDOC contract enumerates for `normalize_events`) because
  `reconstruct_possessions`/its segments need the real home/away identity to
  compute DEFENSE_TEAM_ID and OFFENSE_IS_HOME and are not handed
  `game_teams` directly -- see the judgment-call note in the handback report.
* PTS_HOME/PTS_AWAY are EVENT-SEMANTIC, not a scoreboard delta: a made shot
  scores SHOT_VALUE, a made regular/technical/flagrant/clear-path free throw
  scores 1, credited to the side of TEAM_ID; everything else scores 0. This is
  necessary because the raw per-row scoreboard snapshot is not reliably
  ordered within a single clock instant (verified on 2023-24 game 0022300055:
  a made free throw's row already reflects its own point, but a later
  technical free throw at the identical ELAPSED shows a lower, stale total).
  SCORE_HOME/SCORE_AWAY are the per-game cumulative sums of these event
  points; OBS_SCORE_HOME/OBS_SCORE_AWAY keep the raw observed scoreboard
  (scoring-action rows only, NaN elsewhere, no forward fill) purely as
  reconciliation evidence in `scoring_ledger`, never as the ledger itself.
* IMPLIED POSSESSION CHANGE: control of the open possession is the team of its
  first control event (made/missed shot, non-technical/flagrant/clear-path free
  throw, turnover, or offensive rebound) and is kept by same-team events. If a
  control event (made shot, missed shot, turnover, or regular free throw) by
  the OTHER team arrives with no closing event between -- most often a missing
  rebound row (2017-18 0021700002) -- the open possession is closed at the
  IMMEDIATELY PRECEDING event with OUTCOME 'implied_change', OFFENSE = the team
  that had been in control, and the current event starts a fresh possession.
  Technical/flagrant/clear-path free throws and rebounds never trigger this
  (rebounds keep their own rules); it never fires inside the and-one
  pending-made-shot window.
* FT TRIP MISLABEL: a regular free throw with FT_NUM > 1, by the same team as
  the offense of a possession that JUST closed with outcome 'free_throw_made'
  or 'and_one' at the identical ELAPSED, with nothing but non-decisive/
  administrative events accumulated since, is really a continuation of that
  same trip mislabeled by the source as two separate trips (2017-18
  0021700001: 'Tatum FT 1 of 1' then 'Tatum FT 2 of 2' at one ELAPSED -- the
  first was really 1 of 2). The closed possession is reopened (popped and
  reprocessed) rather than folded-and-kept-closed, so the normal terminal
  logic decides its fate correctly either way: made final keeps it closed on
  this event; missed final leaves it live exactly like any other missed final
  free throw, so the ensuing rebound decides.
* A game is ADMITTED only once its derived final score matches the box score,
  every scoring attempt resolved to a known team (and a made-shot's
  SHOT_VALUE in {2, 3}), every PERIOD CHECKPOINT agrees (the derived score at
  the period's last event equals the max observed scoreboard of that period,
  per side; per-instant agreement is a reported diagnostic because the feed
  stamps some snapshots with the next instant's score), the game's final
  period contains a period-end event, and
  nothing scoring follows that period-end (a real feed can trail a
  non-scoring administrative row -- e.g. Instant Replay / Support Ruling --
  after the true close; `reconstruct_possessions` folds any such trailing
  events into the last possession rather than opening a new one for them).
"""

import re

import numpy as np
import pandas as pd

from scripts.nba_value.analysis.audit_rapm_exposure_units import GAME_ACCOUNTING_COLUMNS

NON_DECISIVE_ACTIONS = frozenset(
    {"foul", "substitution", "timeout", "jump_ball", "violation", "other"}
)

_ACTION_MAP = {
    "made shot": "made_shot",
    "missed shot": "missed_shot",
    "free throw": "free_throw",
    "rebound": "rebound",
    "turnover": "turnover",
    "foul": "foul",
    "substitution": "substitution",
    "period": "period",
    "jump ball": "jump_ball",
    "violation": "violation",
    "timeout": "timeout",
}


def _v(x):
    """Scalar NA of any dtype (Int64/boolean/float/object) -> None; else x."""
    return None if pd.isna(x) else x


def _same_team(a, b):
    return a is not None and b is not None and a == b


def _gid(s: pd.Series) -> pd.Series:
    return s.astype(str).str.zfill(10)


def _norm_action(raw) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "other"
    s = " ".join(str(raw).strip().lower().split())
    return _ACTION_MAP.get(s, "other")


def _parse_ft_kind(subtype):
    s = "" if subtype is None or (isinstance(subtype, float) and pd.isna(subtype)) else str(subtype)
    low = s.lower()
    if "technical" in low:
        kind = "technical"
    elif "flagrant" in low:
        kind = "flagrant"
    elif "clear path" in low:
        kind = "clear_path"
    elif "away from play" in low:
        kind = "away_from_play"
    elif "transition take" in low:
        kind = "transition_take"
    else:
        kind = None
    m = re.search(r"(\d+)\s+of\s+(\d+)", low)
    num, of = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    if kind is None:
        kind = "regular" if m else "unknown"
    if kind == "technical":
        num, of = None, None
    return kind, num, of


def normalize_events(events: pd.DataFrame, game_teams: pd.DataFrame, player_team: pd.DataFrame) -> pd.DataFrame:
    """One row per event, ordered, with derived ACTION/TEAM_ID/FT_*/lineup columns.

    `game_teams`: GAME_ID, HOME_TEAM_ID, AWAY_TEAM_ID.
    `player_team`: GAME_ID, PLAYER_ID, TEAM_ID (from the GameRotation feed).
    """
    e = events.copy()
    e["GAME_ID"] = _gid(e["gameId"])
    e["PERIOD"] = pd.to_numeric(e["period"], errors="raise").astype("Int64")
    e["ELAPSED"] = pd.to_numeric(e["event_time"], errors="coerce")
    order_raw = e["orderNumber"] if "orderNumber" in e.columns else e["actionNumber"]
    e["_ORDER"] = pd.to_numeric(order_raw, errors="coerce")
    e = e.sort_values(["GAME_ID", "PERIOD", "ELAPSED", "_ORDER"], kind="mergesort").reset_index(drop=True)
    e["SEQ"] = e.groupby("GAME_ID").cumcount()
    # Order evidence: a row whose scorer entry number is below one already placed
    # before it by clock time is an ORDER_INVERSION -- time order and entry order
    # disagree (e.g. scorer-inserted correction rows), and neither is authoritative.
    e["ORDER_NUMBER"] = e["_ORDER"]
    prior_max = e.groupby(["GAME_ID", "PERIOD"])["ORDER_NUMBER"].transform(lambda s: s.cummax().shift())
    e["ORDER_INVERSION"] = (e["ORDER_NUMBER"] < prior_max).to_numpy(dtype=bool)

    e["ACTION"] = e["actionType"].map(_norm_action)
    e["SUBTYPE_RAW"] = e["subType"]

    gt = game_teams.copy()
    gt["GAME_ID"] = _gid(gt["GAME_ID"])
    gt = gt.set_index("GAME_ID")
    e["HOME_TEAM_ID"] = e["GAME_ID"].map(gt["HOME_TEAM_ID"])
    e["AWAY_TEAM_ID"] = e["GAME_ID"].map(gt["AWAY_TEAM_ID"])

    team_id_raw = pd.to_numeric(e["teamId"], errors="coerce")
    person_id = pd.to_numeric(e["personId"], errors="coerce")
    # Legacy V3 team-level events (team rebounds, shot-clock turnovers, timeouts,
    # team fouls/violations) carry teamId 0 and the TEAM id in personId.
    legacy_team_event = (
        (team_id_raw == 0)
        & ((person_id == e["HOME_TEAM_ID"]) | (person_id == e["AWAY_TEAM_ID"]))
    )
    team_id = team_id_raw.copy()
    team_id[team_id_raw == 0] = np.nan
    team_id = team_id.mask(legacy_team_event, person_id)
    e["TEAM_ID"] = team_id.astype("Int64")
    # An 'Excess Timeout Turnover' row carries no team at all (2020-21 0022000215);
    # the rule charges it to the team that requested the timeout, whose timeout row
    # the feed logs just before. No earlier team timeout in the game: stays <NA>.
    excess = ((e["ACTION"] == "turnover") & e["TEAM_ID"].isna()
              & e["subType"].astype("string").str.lower().str.contains("excess timeout").isin([True]))
    if excess.any():
        timeout_team = e["TEAM_ID"].where(e["ACTION"] == "timeout")
        last_timeout_team = timeout_team.groupby(e["GAME_ID"]).ffill()
        e.loc[excess, "TEAM_ID"] = last_timeout_team[excess]
    e["PERSON_ID"] = person_id.astype("Int64")

    e["SHOT_VALUE"] = pd.to_numeric(e["shotValue"], errors="coerce")

    is_ft = e["ACTION"] == "free_throw"
    shot_result = e["shotResult"] if "shotResult" in e.columns else pd.Series(pd.NA, index=e.index)
    sr = shot_result.astype("string")
    has_sr = sr.notna() & (sr.str.strip() != "")
    desc = e["description"] if "description" in e.columns else pd.Series(pd.NA, index=e.index)
    desc_s = desc.astype("string")
    # The feed's miss marker is the uppercase token 'MISS ' -- case-sensitive: a
    # player named Missi ('Missi Free Throw 1 of 2 (1 PTS)', 2024-25) is a make.
    miss_by_desc = desc_s.str.strip().str.match(r"MISS\s").isin([True])
    # Legacy V3 writes '(N PTS)' on every made free throw; a row with neither that
    # suffix nor a MISS prefix (2015-16 0021500391: bare 'Free Throw 2 of 2') is
    # not evidence of a make.
    pts_by_desc = desc_s.str.contains(r"\(\d+ PTS\)", regex=True).isin([True])

    ft_made = pd.Series(pd.NA, index=e.index, dtype="boolean")
    source = pd.Series(pd.NA, index=e.index, dtype="object")
    idx_sr = is_ft & has_sr
    ft_made[idx_sr] = sr[idx_sr].str.strip().str.casefold() == "made"
    source[idx_sr] = "shot_result"
    idx_made = is_ft & ~has_sr & pts_by_desc & ~miss_by_desc
    ft_made[idx_made] = True
    source[idx_made] = "description_pts"
    idx_miss = is_ft & ~has_sr & miss_by_desc & ~pts_by_desc
    ft_made[idx_miss] = False
    source[idx_miss] = "description_miss"
    # Neither marker: a missed free throw is the only one followed by a rebound, so
    # a rebound as the next non-administrative event resolves it as missed; with
    # no such evidence the outcome stays unknown (unresolved scoring, quarantine).
    bare = is_ft & ~has_sr & ~pts_by_desc & ~miss_by_desc
    source[is_ft & ~has_sr & pts_by_desc & miss_by_desc] = "unknown"   # contradictory markers
    if bare.any():
        admin = e["ACTION"].isin(["substitution", "timeout", "other"])
        decisive = e.loc[~admin].groupby("GAME_ID")
        next_action = decisive["ACTION"].shift(-1).reindex(e.index)
        prev_action = decisive["ACTION"].shift(1).reindex(e.index)
        prev_elapsed = decisive["ELAPSED"].shift(1).reindex(e.index)
        inferred_next = bare & (next_action == "rebound").isin([True])
        # A late-inserted bare FT can sit after its own rebound at the same clock
        # (2015-16 0021501180, 2016-17 0021600158; the scoreboard confirms no point).
        inferred_adjacent = (bare & ~inferred_next & (prev_action == "rebound").isin([True])
                             & (prev_elapsed == e["ELAPSED"]).isin([True]))
        ft_made[inferred_next | inferred_adjacent] = False
        source[inferred_next] = "inferred_next_rebound"
        source[inferred_adjacent] = "inferred_adjacent_rebound"
        source[bare & ~inferred_next & ~inferred_adjacent] = "unknown"
    e["FT_MADE"] = ft_made
    e["FT_OUTCOME_SOURCE"] = source

    kind = pd.Series(pd.NA, index=e.index, dtype="object")
    num = pd.Series(pd.NA, index=e.index, dtype="Int64")
    of_ = pd.Series(pd.NA, index=e.index, dtype="Int64")
    if is_ft.any():
        # Legacy names the kind in subType ('Free Throw Technical'); the live feed
        # keeps subType as 'k of n' and names it in `descriptor` ('technical',
        # 'flagrant', 'clear-path', 'away-from-play', 'transition take').
        ft_text = e.loc[is_ft, "SUBTYPE_RAW"].astype("string")
        if "descriptor" in e.columns:
            # Text join (na_rep): a row without a descriptor keeps its subType text.
            ft_text = ft_text.str.cat(e.loc[is_ft, "descriptor"].astype("string").str.replace("-", " "),
                                      sep=" ", na_rep="")
        parsed = ft_text.map(_parse_ft_kind)
        kind.loc[is_ft] = parsed.map(lambda t: t[0])
        num.loc[is_ft] = pd.array([t[1] for t in parsed], dtype="Int64")
        of_.loc[is_ft] = pd.array([t[2] for t in parsed], dtype="Int64")
    # Retained-possession fouls award 1 FT and the fouled team KEEPS the ball, like a
    # flagrant/clear-path foul, but the feed labels the FT 'Free Throw 1 of 1':
    #   away from play   (2015-16 0021500038; legacy subType 'Away From Play',
    #                     live descriptor 'away-from-play')
    #   transition take  (rule from 2022-23, 0022200034; legacy subType 'Transition
    #                     Take', live descriptor 'transition take'). A plain 'take'
    #                     foul is a bonus 2-FT trip and is NOT retained.
    #   inbound           (2016-17 0021600043; legacy subType 'Inbound', description
    #                     'IN.FOUL'): a defender's foul before the throw-in is
    #                     released; 1 FT and the throw-in team keeps the ball.
    # Only a 1-shot award is relabelled, so an inbound foul penalized as a bonus
    # 2-FT trip stays a regular trip. The most recent non-technical foul at the same
    # instant decides: a technical awards its own 'Free Throw Technical' and never
    # the 1-shot award (2021-22 0022100543: away-from-play foul, then a technical).
    foul_text = (e["subType"].astype("string").str.lower().str.replace("-", " ").str.replace(".", " ")
                 + " " + desc_s.str.lower().str.replace("-", " ").str.replace(".", " "))
    if "descriptor" in e.columns:
        foul_text = foul_text + " " + e["descriptor"].astype("string").str.lower().str.replace("-", " ")
    is_foul = e["ACTION"] == "foul"
    is_technical_foul = is_foul & foul_text.str.contains("technical").isin([True])
    marker = pd.Series(pd.NA, index=e.index, dtype="object")
    marker[is_foul & ~is_technical_foul] = "none"
    for phrase, retained_kind in RETAINED_POSSESSION_FOULS.items():
        marker[is_foul & ~is_technical_foul & foul_text.str.contains(phrase).isin([True])] = retained_kind
    instant = [e["GAME_ID"], e["ELAPSED"]]
    last_foul = marker.groupby(instant).ffill()
    one_shot = is_ft & (kind == "regular") & (of_ == 1).isin([True])
    for retained_kind in RETAINED_POSSESSION_FOULS.values():
        kind[one_shot & (last_foul == retained_kind).isin([True])] = retained_kind
    # A 1-shot FT whose only earlier foul at the instant is a technical is that
    # technical's FT mislabelled 'Free Throw 1 of 1' (2017-18 0021700244: 'Mitchell
    # T.FOUL', 'Redick Free Throw 1 of 1', PHI keeps the ball) -- unless the shooting
    # team also scored a field goal at that instant, which makes it an and-one.
    technical_seen = is_technical_foul.astype(int).groupby(instant).cumsum() > 0
    made_at_instant = (e["ACTION"] == "made_shot").groupby(
        [e["GAME_ID"], e["ELAPSED"], e["TEAM_ID"]], dropna=False).transform("any")
    kind[one_shot & last_foul.isna() & technical_seen & ~made_at_instant] = "technical"
    e["FT_KIND"] = kind
    e["FT_NUM"] = num
    e["FT_OF"] = of_

    subtype_l = e["SUBTYPE_RAW"].astype("string").str.lower()
    e["PERIOD_END"] = (e["ACTION"] == "period") & subtype_l.str.contains("end", na=False)

    # Scoreboard evidence comes only from scoring actions: non-scoring rows (e.g. an
    # Instant Replay) can carry a snapshot stamped before the events that produced it.
    scoring_action = e["ACTION"].isin(["made_shot", "free_throw"])
    e["OBS_SCORE_HOME"] = pd.to_numeric(e["scoreHome"], errors="coerce").where(scoring_action)
    e["OBS_SCORE_AWAY"] = pd.to_numeric(e["scoreAway"], errors="coerce").where(scoring_action)

    # Points are event-semantic, not a scoreboard delta: verified on 2023-24 game
    # 0022300055, the raw per-row scoreboard snapshots are NOT chronologically
    # ordered within a single clock instant (a made free throw's row shows the
    # already-incremented total while a later technical free throw's row at the
    # identical ELAPSED shows a lower, stale total). A delta of adjacent snapshots
    # is therefore not a usable ledger; the observed scoreboard is reconciled
    # instead as periodic CHECKPOINTS in scoring_ledger.
    is_made_shot = e["ACTION"] == "made_shot"
    is_ft = e["ACTION"] == "free_throw"
    # isin([True]) selects only KNOWN-true comparisons; an unknown stays unselected
    # and is surfaced below, never read as a default.
    is_ft_made = is_ft & e["FT_MADE"].isin([True])
    ft_outcome_unknown = is_ft & e["FT_MADE"].isna()
    home_match = (e["TEAM_ID"] == e["HOME_TEAM_ID"]).isin([True])
    away_match = (e["TEAM_ID"] == e["AWAY_TEAM_ID"]).isin([True])
    team_known = home_match | away_match
    valid_shot_value = e["SHOT_VALUE"].isin([2, 3])

    # A free throw whose make/miss cannot be determined is unresolved scoring
    # evidence (it may carry a point), never a silent zero.
    e["SCORING_UNRESOLVED"] = ft_outcome_unknown | ((is_made_shot | is_ft_made) & (
        ~team_known | (is_made_shot & ~valid_shot_value)))

    made_shot_ok = is_made_shot & team_known & valid_shot_value
    ft_made_ok = is_ft_made & team_known
    shot_value_f = e["SHOT_VALUE"].astype(float)
    pts_home = pd.Series(0.0, index=e.index)
    pts_away = pd.Series(0.0, index=e.index)
    pts_home[made_shot_ok & home_match] = shot_value_f[made_shot_ok & home_match]
    pts_away[made_shot_ok & away_match] = shot_value_f[made_shot_ok & away_match]
    pts_home[ft_made_ok & home_match] = 1.0
    pts_away[ft_made_ok & away_match] = 1.0
    e["PTS_HOME"] = pts_home
    e["PTS_AWAY"] = pts_away

    e["SCORE_HOME"] = e.groupby("GAME_ID")["PTS_HOME"].cumsum()
    e["SCORE_AWAY"] = e.groupby("GAME_ID")["PTS_AWAY"].cumsum()

    pt = player_team.copy()
    pt["GAME_ID"] = _gid(pt["GAME_ID"])
    pt_map = dict(zip(zip(pt["GAME_ID"], pt["PLAYER_ID"].astype(int)), pt["TEAM_ID"]))

    def _split_lineup(row):
        h = row["home_lineup"]
        a = row["away_lineup"]
        pool = (list(h) if h is not None else []) + (list(a) if a is not None else [])
        pool = list(dict.fromkeys(int(p) for p in pool))
        home_t, away_t = row["HOME_TEAM_ID"], row["AWAY_TEAM_ID"]
        if len(pool) != 10 or pd.isna(home_t) or pd.isna(away_t):
            return (None, None, False)
        home_players, away_players = [], []
        for p in pool:
            t = pt_map.get((row["GAME_ID"], p))
            if t == home_t:
                home_players.append(p)
            elif t == away_t:
                away_players.append(p)
            else:
                return (None, None, False)
        if len(home_players) != 5 or len(away_players) != 5:
            return (None, None, False)
        return (tuple(sorted(home_players)), tuple(sorted(away_players)), True)

    lineup_results = e.apply(_split_lineup, axis=1)
    e["HOME_ON"] = lineup_results.map(lambda t: t[0])
    e["AWAY_ON"] = lineup_results.map(lambda t: t[1])
    e["LINEUP_VALID"] = lineup_results.map(lambda t: t[2])

    return e[[
        "GAME_ID", "SEQ", "PERIOD", "ELAPSED", "ACTION", "SUBTYPE_RAW", "TEAM_ID", "PERSON_ID",
        "SHOT_VALUE", "FT_MADE", "FT_OUTCOME_SOURCE", "FT_KIND", "FT_NUM", "FT_OF", "PERIOD_END",
        "SCORE_HOME", "SCORE_AWAY", "PTS_HOME", "PTS_AWAY", "SCORING_UNRESOLVED",
        "OBS_SCORE_HOME", "OBS_SCORE_AWAY",
        "HOME_ON", "AWAY_ON", "LINEUP_VALID", "HOME_TEAM_ID", "AWAY_TEAM_ID",
        "ORDER_NUMBER", "ORDER_INVERSION",
    ]].copy()


def _period_checkpoints(g: pd.DataFrame, box: dict) -> tuple[int, int, int, bool]:
    """Per-period scoreboard checkpoints for one game, only where the feed's own
    scoreboard is reliable evidence.

    Per side, the observed scoreboard is evidence only if its final value equals the
    box score (2017-18 0021700025: the feed's home score ends 103 against a box and
    event total of 120), and only for periods AFTER its last self-contradiction -- a
    value lower than the one it showed just before (2021-22 0022100016: a phantom away point
    the feed later rescinds) -- and after it, only once the feed agrees with the events
    again (2022-23 0022200107: Q3 rows stamped with Q4 scores).
    A checked period's derived end score must equal its max observed score.
    Returns (checked, mismatches, unchecked, every_side_final_matches_box)."""
    per = g.groupby("PERIOD", sort=True).agg(
        END_HOME=("SCORE_HOME", "last"), END_AWAY=("SCORE_AWAY", "last"),
        OBS_HOME=("OBS_SCORE_HOME", "max"), OBS_AWAY=("OBS_SCORE_AWAY", "max"))
    checked = mismatches = unchecked = 0
    final_matches = True
    for side in ("HOME", "AWAY"):
        obs = g[f"OBS_SCORE_{side}"].dropna()
        if obs.empty:
            continue
        # A self-contradiction is a value lower than the one just before it: the
        # point where the feed corrected itself (not "lower than any earlier value",
        # which would let one early corrupt snapshot silence every later period).
        contradicted = obs < obs.shift()
        trusted_after = 0
        if contradicted.any():
            # After its last self-correction the feed is evidence again only once it
            # agrees with the events at some row (2022-23 0022200107: five Q3 rows
            # carry Q4-end stamps whose points the feed never counts, so it runs 3/5
            # low through Q4 and re-anchors only in overtime). Every period up to the
            # last row before that re-anchor is unchecked.
            tail = obs.iloc[obs.index.get_loc(contradicted[contradicted].index[-1]):]
            agrees = (tail == g.loc[tail.index, f"SCORE_{side}"]).to_numpy()
            unreliable = tail.index[:agrees.argmax()] if agrees.any() else tail.index
            trusted_after = int(g.loc[unreliable if len(unreliable) else tail.index[:1], "PERIOD"].max())
        side_final_ok = bool(obs.iloc[-1] == box[side])
        final_matches = final_matches and side_final_ok
        for period, r in per.iterrows():
            if pd.isna(r[f"OBS_{side}"]):
                continue
            if side_final_ok and period > trusted_after:
                checked += 1
                mismatches += int(r[f"OBS_{side}"] != r[f"END_{side}"])
            else:
                unchecked += 1
    return checked, mismatches, unchecked, final_matches


def scoring_ledger(norm: pd.DataFrame, box: pd.DataFrame):
    """Per-scoring-event rows (plus unresolved scoring attempts) and a per-game
    ADMITTED/QUARANTINED status. Points are event-semantic (see normalize_events);
    admission reconciles the derived running score to the observed scoreboard at
    each (GAME_ID, PERIOD, ELAPSED) CHECKPOINT rather than trusting a raw delta.

    `box`: GAME_ID, HOME_PTS, AWAY_PTS.
    """
    n = norm.sort_values(["GAME_ID", "SEQ"], kind="mergesort").reset_index(drop=True)

    resolved = n[(n["PTS_HOME"] > 0) | (n["PTS_AWAY"] > 0)].copy()
    home_side = resolved["PTS_HOME"] > 0
    resolved["SCORING_TEAM_ID"] = np.where(home_side, resolved["HOME_TEAM_ID"], resolved["AWAY_TEAM_ID"])
    resolved["SCORING_TEAM_ID"] = resolved["SCORING_TEAM_ID"].astype("Int64")
    resolved["POINTS"] = np.where(home_side, resolved["PTS_HOME"], resolved["PTS_AWAY"]).astype(float)

    unresolved = n[n["SCORING_UNRESOLVED"]].copy()
    unresolved["SCORING_TEAM_ID"] = pd.Series(pd.NA, index=unresolved.index, dtype="Int64")
    unresolved["POINTS"] = np.nan

    scoring_events = (
        pd.concat([resolved, unresolved])
        .sort_values(["GAME_ID", "SEQ"], kind="mergesort")[[
            "GAME_ID", "SEQ", "SCORING_TEAM_ID", "POINTS", "LINEUP_VALID", "ACTION",
        ]]
        .rename(columns={"ACTION": "SOURCE_ACTION"})
        .reset_index(drop=True)
    )

    box_idx = box.copy()
    box_idx["GAME_ID"] = _gid(box_idx["GAME_ID"])
    box_idx = box_idx.set_index("GAME_ID")

    # Checkpoints: every (game, period, elapsed) instant with at least one observed
    # scoreboard value on either side. A mismatch compares the derived cumulative
    # score at the END of the instant (the last event's SCORE_HOME/AWAY, since rows
    # keep SEQ order within a group) against the MAX observed value of that side
    # within the instant -- the raw per-row snapshots are not reliably ordered
    # within one clock instant, but the end-of-instant total and the highest
    # observed value must still agree once every event in the instant is applied.
    inst = n.groupby(["GAME_ID", "PERIOD", "ELAPSED"], sort=False).agg(
        END_HOME=("SCORE_HOME", "last"), END_AWAY=("SCORE_AWAY", "last"),
        OBS_H=("OBS_SCORE_HOME", "max"), OBS_A=("OBS_SCORE_AWAY", "max"),
    ).reset_index()
    inst["HAS_OBS"] = inst["OBS_H"].notna() | inst["OBS_A"].notna()
    inst["MISMATCH"] = inst["HAS_OBS"] & (
        (inst["OBS_H"].notna() & (inst["OBS_H"] != inst["END_HOME"]))
        | (inst["OBS_A"].notna() & (inst["OBS_A"] != inst["END_AWAY"]))
    )
    per_game_cp = inst.groupby("GAME_ID", sort=False).agg(
        INSTANT_CHECKPOINTS=("HAS_OBS", "sum"), INSTANT_MISMATCHES=("MISMATCH", "sum"))
    # Gating checkpoint is PER PERIOD: the source stamps some snapshots with a score
    # that already includes the NEXT instant's points (2023-24: 0022300405 /
    # 0022300510 / 0022300786, each two adjacent instants, final score exact), so
    # per-instant agreement is stricter than the feed supports. Scores are
    # cumulative, so any missed, extra or misattributed point still persists to
    # its period's end: the derived score at the period's last event must equal
    # the max observed score of that period, per side. Instant mismatches remain a
    # reported diagnostic.
    rows = []
    for gid, g in n.groupby("GAME_ID", sort=False):
        last = g.iloc[-1]
        final_home, final_away = float(last["SCORE_HOME"]), float(last["SCORE_AWAY"])
        unresolved_n = int(g["SCORING_UNRESOLVED"].sum())
        instant_mismatches = (int(per_game_cp.loc[gid, "INSTANT_MISMATCHES"])
                              if gid in per_game_cp.index else 0)
        if gid in box_idx.index:
            box_home = float(box_idx.loc[gid, "HOME_PTS"])
            box_away = float(box_idx.loc[gid, "AWAY_PTS"])
        else:
            box_home = box_away = np.nan
        checkpoints, mismatches, unchecked, final_matches = _period_checkpoints(
            g, {"HOME": box_home, "AWAY": box_away})

        # The final period must contain a period-end event, and nothing scoring may
        # follow it (a real feed can trail an administrative row -- e.g. Instant
        # Replay / Support Ruling -- after the true final period-end).
        # The final period is the last one with a real event: a lone period-start
        # marker with nothing after it (2015-16 0021500916, a spurious 'Start of
        # 1st OT' stamped before the regulation end) is not a period played.
        played = g[g["ACTION"] != "period"]
        max_period = played["PERIOD"].max() if len(played) else g["PERIOD"].max()
        final_period = g[g["PERIOD"] == max_period]
        has_period_end = bool(final_period["PERIOD_END"].any())
        scoring_after_end = False
        if has_period_end:
            end_seq = final_period.loc[final_period["PERIOD_END"], "SEQ"].max()
            after = g[g["SEQ"] > end_seq]
            after_scoring = (after["ACTION"] == "made_shot") | (
                (after["ACTION"] == "free_throw") & after["FT_MADE"].isin([True]))
            scoring_after_end = bool(after_scoring.any())

        reasons = []
        if pd.isna(box_home) or final_home != box_home or final_away != box_away:
            reasons.append("final_score_mismatch_box")
        if unresolved_n > 0:
            reasons.append("unresolved_scoring_event")
        if mismatches > 0:
            reasons.append("scoreboard_checkpoint_mismatch")
        if not has_period_end:
            reasons.append("stream_missing_final_period_end")
        elif scoring_after_end:
            reasons.append("scoring_after_final_period_end")
        status = "QUARANTINED" if reasons else "ADMITTED"
        rows.append({
            "GAME_ID": gid, "FINAL_HOME": final_home, "FINAL_AWAY": final_away,
            "BOX_HOME": box_home, "BOX_AWAY": box_away,
            "UNRESOLVED_SCORING_EVENTS": unresolved_n,
            "CHECKPOINTS": checkpoints, "CHECKPOINT_MISMATCHES": mismatches,
            "SCOREBOARD_UNCHECKED_PERIODS": unchecked,
            "SCOREBOARD_FINAL_MATCHES_BOX": final_matches,
            "INSTANT_CHECKPOINT_MISMATCHES": instant_mismatches,
            "HAS_PERIOD_END": has_period_end,
            "STATUS": status, "REASON": "; ".join(reasons) if reasons else None,
        })
    game_status = pd.DataFrame(rows)
    return scoring_events, game_status


def _append_possession(possessions, gid, period, poss_idx, start_i, end_i, outcome, offense_team,
                        rows, home_t, away_t):
    seg = rows.iloc[start_i:end_i + 1]
    if offense_team is None:
        defense_team = None
    elif offense_team == home_t:
        defense_team = away_t
    elif offense_team == away_t:
        defense_team = home_t
    else:
        defense_team = None
    possessions.append({
        "GAME_ID": gid, "PERIOD": period, "POSS_IDX": poss_idx,
        "START_SEQ": int(rows.iloc[start_i]["SEQ"]), "END_SEQ": int(rows.iloc[end_i]["SEQ"]),
        "OUTCOME": outcome, "OFFENSE_TEAM_ID": offense_team, "DEFENSE_TEAM_ID": defense_team,
        "HOME_PTS": float(seg["PTS_HOME"].sum()), "AWAY_PTS": float(seg["PTS_AWAY"].sum()),
    })


def _fold_period_tail(possessions: list, rows: pd.DataFrame, i: int, period) -> int:
    """Fold rows that follow a period end but still carry that period (a post-buzzer
    team rebound, replay rulings) into the possession the period end closed, so no
    possession ever spans two periods (2015-16 0021500002: 'End of 1st Period' then
    'Cavaliers Rebound', both period 1). Returns the index of the last folded row."""
    last = possessions[-1]
    j = i + 1
    while j < len(rows) and rows.iloc[j]["PERIOD"] == period:
        last["END_SEQ"] = int(rows.iloc[j]["SEQ"])
        last["HOME_PTS"] += float(rows.iloc[j]["PTS_HOME"])
        last["AWAY_PTS"] += float(rows.iloc[j]["PTS_AWAY"])
        j += 1
    return j - 1


# Foul phrase (normalized text) -> FT_KIND of the 1-FT trip it awards; the fouled
# team keeps possession, so these FTs never end a possession.
RETAINED_POSSESSION_FOULS = {"away from play": "away_from_play", "transition take": "transition_take",
                             "inbound": "inbound"}
# Awards whose shooting team keeps the ball afterwards (technical FTs are not awards
# to the fouled team's possession at all, so they are excluded).
RETAINED_AWARD_KINDS = ("flagrant", "clear_path", "away_from_play", "transition_take", "inbound")
RETAINED_FT_KINDS = ("technical", *RETAINED_AWARD_KINDS, "unknown")


def _after_own_ft_end(possessions: list, rows: pd.DataFrame, start_i: int, i: int, row,
                      team, period) -> bool:
    """This row is by the team whose possession JUST ended on its own made free
    throw, at the same instant, with only non-decisive rows between."""
    if team is None or not possessions:
        return False
    prev = possessions[-1]
    return bool(prev["PERIOD"] == period
                and prev["OUTCOME"] in ("free_throw_made", "and_one")
                and team == prev["OFFENSE_TEAM_ID"]
                and rows.iloc[prev["END_SEQ"]]["ELAPSED"] == row["ELAPSED"]
                and rows.iloc[start_i:i]["ACTION"].isin(NON_DECISIVE_ACTIONS).all())


def _continues_trip(possessions: list, rows: pd.DataFrame, start_i: int, i: int, row,
                    team, kind, period) -> bool:
    """An FT that continues the same team's FT-ended possession: a later FT of a
    mislabeled trip (FT_NUM > 1), or a new 1-shot award -- regular or retained-possession
    (2016-17 0021601180: made FT 2 of 2, away-from-play foul, FT 1 of 1, same team
    keeps the ball) -- after a same-instant foul."""
    num = _v(row["FT_NUM"])
    fouled_again = rows.iloc[start_i:i]["ACTION"].eq("foul").any()
    if kind == "regular" and num is not None:
        continues = num > 1 or fouled_again
    else:
        continues = kind in RETAINED_AWARD_KINDS and fouled_again
    return continues and _after_own_ft_end(possessions, rows, start_i, i, row, team, period)


# Events by which a team shows it has the ball.
CONTROL_ACTIONS = ("made_shot", "missed_shot", "turnover")
SAME_TEAM_REPEAT_COLUMNS = ["GAME_ID", "PERIOD", "POSS_IDX", "OFFENSE_TEAM_ID", "PREV_OUTCOME",
                            "TRANSFER_SEQ", "NEXT_SEQ", "NEXT_ACTION", "GAP_SECONDS", "IDENTITY_OK",
                            "VERIFIED"]


def person_team_ids(norm: pd.DataFrame, player_team: pd.DataFrame) -> pd.Series:
    """Each row's acting player's team in the game rotation (aligned to `norm`);
    <NA> for team-level rows and players the rotation does not list."""
    roster = player_team[["GAME_ID", "PLAYER_ID", "TEAM_ID"]].copy()
    roster["GAME_ID"] = _gid(roster["GAME_ID"])
    roster = roster.astype({"PLAYER_ID": "Int64", "TEAM_ID": "Int64"}).drop_duplicates(["GAME_ID", "PLAYER_ID"])
    keyed = norm[["GAME_ID", "PERSON_ID"]].reset_index()
    merged = keyed.merge(roster.rename(columns={"PLAYER_ID": "PERSON_ID", "TEAM_ID": "PERSON_TEAM_ID"}),
                         on=["GAME_ID", "PERSON_ID"], how="left")
    return merged.set_index("index")["PERSON_TEAM_ID"].reindex(norm.index)


def same_team_repeats(possessions: pd.DataFrame, norm: pd.DataFrame,
                      player_team: pd.DataFrame) -> pd.DataFrame:
    """One row per pair of consecutive possessions of the SAME team in a period.

    VERIFIED is the policy source-absence-v2 evidence that the opponent's possession
    between them is absent from the source (2017-18 0021700022: BKN scores at 11:23
    of Q1 and its next row is its own missed 3 at 10:52):
      * the first possession ended by giving the ball away (TRANSFER_OUTCOMES);
      * the next possession's first row is that same team's control event (made or
        missed shot, turnover) at a strictly LATER clock, so no row of any kind lies
        between -- a same-clock repeat is an ordering artefact, never absence;
      * identity holds on both rows: the acting player is on the row's team in the
        game rotation, or the row is a team-level event naming that team."""
    if possessions.empty:
        return pd.DataFrame(columns=SAME_TEAM_REPEAT_COLUMNS)
    p = possessions.sort_values(["GAME_ID", "START_SEQ"], kind="mergesort").reset_index(drop=True)
    by = p.groupby(["GAME_ID", "PERIOD"], sort=False)
    p["PREV_TEAM"] = by["OFFENSE_TEAM_ID"].shift()
    p["PREV_OUTCOME"] = by["OUTCOME"].shift()
    p["TRANSFER_SEQ"] = by["END_SEQ"].shift()
    rep = p[(p["OFFENSE_TEAM_ID"] == p["PREV_TEAM"]).isin([True])].copy()
    if rep.empty:
        return pd.DataFrame(columns=SAME_TEAM_REPEAT_COLUMNS)
    rep["TRANSFER_SEQ"] = rep["TRANSFER_SEQ"].astype("int64")
    rep["NEXT_SEQ"] = rep["START_SEQ"]
    ev = norm[["GAME_ID", "SEQ", "ELAPSED", "ACTION", "TEAM_ID", "PERSON_ID"]].assign(
        PERSON_TEAM_ID=person_team_ids(norm, player_team))
    ev["IDENTITY_OK"] = ((ev["PERSON_TEAM_ID"] == ev["TEAM_ID"]).isin([True])
                         | (ev["PERSON_ID"] == ev["TEAM_ID"]).isin([True]))
    t = ev.rename(columns=lambda c: c if c in ("GAME_ID", "SEQ") else f"T_{c}")
    n = ev.rename(columns=lambda c: c if c in ("GAME_ID", "SEQ") else f"N_{c}")
    rep = (rep.merge(t, left_on=["GAME_ID", "TRANSFER_SEQ"], right_on=["GAME_ID", "SEQ"], how="left")
              .drop(columns="SEQ")
              .merge(n, left_on=["GAME_ID", "NEXT_SEQ"], right_on=["GAME_ID", "SEQ"], how="left")
              .drop(columns="SEQ"))
    rep["NEXT_ACTION"] = rep["N_ACTION"]
    rep["GAP_SECONDS"] = rep["N_ELAPSED"] - rep["T_ELAPSED"]
    rep["IDENTITY_OK"] = rep["T_IDENTITY_OK"].isin([True]) & rep["N_IDENTITY_OK"].isin([True])
    rep["VERIFIED"] = (rep["PREV_OUTCOME"].isin(TRANSFER_OUTCOMES)
                       & rep["NEXT_ACTION"].isin(CONTROL_ACTIONS)
                       & (rep["N_TEAM_ID"] == rep["OFFENSE_TEAM_ID"]).isin([True])
                       & (rep["GAP_SECONDS"] > 0).isin([True])
                       & rep["IDENTITY_OK"])
    return rep[SAME_TEAM_REPEAT_COLUMNS].reset_index(drop=True)


def classify_alternation_failures(possessions: pd.DataFrame, inversions: pd.Series,
                                  schema: str, repeats: pd.DataFrame) -> dict:
    """GAME_ID -> reason for every game with a period where one team has 2+ more
    possessions than the other (inside a period possessions alternate).

    Policy source-order-v1 (checked first): 'source_order_unresolvable' only when
    every failing period contains an ORDER_INVERSION (time order vs scorer entry
    order disagree, so no order is defensible), every possession in the game is
    attributed, and the feed is the legacy schema.
    Policy source-absence-v2: 'source_possession_unlogged' only when every
    possession is attributed and EVERY same-team repeat in every failing period is
    VERIFIED evidence of an opponent possession absent from the source
    (`same_team_repeats`); the game is removed whole, never given a synthesized
    possession, duration, lineup or score.
    Anything else is 'possession_alternation_unexplained' (a parser gap, never
    excludable). The caller has already admitted the game's scoring (final == box
    by side, all points accounted, no unresolved free throw). `inversions`:
    (GAME_ID, PERIOD) -> count of ORDER_INVERSION rows; `repeats`: GAME_ID, PERIOD,
    VERIFIED per same-team repeat."""
    out = {}
    if possessions.empty:
        return out
    repeats_by_game = {gid: r for gid, r in repeats.groupby("GAME_ID")}
    for gid, g in possessions.groupby("GAME_ID"):
        attributed = g.dropna(subset=["OFFENSE_TEAM_ID"])
        teams = sorted(attributed["OFFENSE_TEAM_ID"].unique())
        failing = []
        for period, gp in attributed.groupby("PERIOD"):
            counts = [int((gp["OFFENSE_TEAM_ID"] == t).sum()) for t in teams]
            counts += [0] * (2 - len(counts))          # a team with no possession here
            if abs(counts[0] - counts[1]) > 1:
                failing.append(period)
        if not failing:
            continue
        complete = len(attributed) == len(g)
        if (schema == "legacy" and complete
                and all(int(inversions.get((gid, per), 0)) > 0 for per in failing)):
            out[gid] = "source_order_unresolvable"
            continue
        r = repeats_by_game.get(gid)
        in_failing = r[r["PERIOD"].isin(failing)] if r is not None else None
        unlogged = (complete and in_failing is not None
                    and set(in_failing["PERIOD"]) == set(failing)
                    and bool(in_failing["VERIFIED"].astype(bool).all()))
        out[gid] = "source_possession_unlogged" if unlogged else "possession_alternation_unexplained"
    return out


TRANSFER_OUTCOMES = {"made_shot", "and_one", "turnover", "defensive_rebound", "free_throw_made"}


def _control_after(possessions: list, period) -> object:
    """Team that gained the ball from the previous possession's terminal event in
    the same period (its defense), or None when there is no such evidence (e.g. a
    period that ends before any control-establishing event)."""
    if not possessions:
        return None
    prev = possessions[-1]
    if prev["PERIOD"] != period or prev["OUTCOME"] not in TRANSFER_OUTCOMES:
        return None
    return prev["DEFENSE_TEAM_ID"]


def _reconstruct_game(rows: pd.DataFrame) -> list:
    n = len(rows)
    gid = rows["GAME_ID"].iloc[0]
    home_t = rows["HOME_TEAM_ID"].iloc[0]
    away_t = rows["AWAY_TEAM_ID"].iloc[0]
    possessions = []
    start_i = 0
    poss_idx = 0
    cur_period = rows.iloc[0]["PERIOD"]
    pending_made = None
    last_miss_team = None
    dead_ball_pending = False
    last_control_team = None

    i = 0
    while i < n:
        row = rows.iloc[i]
        action = row["ACTION"]
        team = _v(row["TEAM_ID"])
        kind = _v(row["FT_KIND"])
        terminal = False
        outcome = None
        offense_team = None

        if pending_made is not None:
            p_idx, p_team = pending_made
            if (action == "free_throw" and kind == "regular" and _v(row["FT_OF"]) == 1
                    and _same_team(team, p_team)):
                pending_made = None
                if bool(_v(row["FT_MADE"])):   # np/pandas bool: compare by value
                    terminal = True
                    outcome = "and_one"
                    offense_team = p_team
                else:
                    # A missed and-one FT is a live ball, like a missed final FT: the
                    # ensuing rebound decides (2017-18 0021700168: the shooting team
                    # rebounds and scores again in the same possession).
                    last_miss_team = team
                    last_control_team = team
                    i += 1
                    continue
            elif (action in NON_DECISIVE_ACTIONS
                  # The feed logs a putback's offensive rebound AFTER the make at the
                  # same clock (2015-16 0021500070): not decisive for the and-one.
                  or (action == "rebound" and _same_team(team, p_team)
                      and row["ELAPSED"] == rows.iloc[p_idx]["ELAPSED"])
                  or (action == "free_throw" and kind in RETAINED_FT_KINDS)
                  or (action == "period" and not bool(row["PERIOD_END"]))):
                if (action == "free_throw" and kind in RETAINED_FT_KINDS and kind != "technical"
                        and _same_team(team, p_team)):
                    # A retained-possession award (flagrant, clear path, away from play,
                    # transition take) to the SCORING team keeps it in control, so the
                    # made shot does not end the possession (2024-25 0022400109: Paul
                    # 3PT, flagrant 1, Paul FT, SAS ball, Wembanyama scores).
                    pending_made = None
                    last_control_team = team
                i += 1
                continue
            else:
                _append_possession(possessions, gid, cur_period, poss_idx, start_i, p_idx,
                                    "made_shot", p_team, rows, home_t, away_t)
                poss_idx += 1
                start_i = p_idx + 1
                if start_i < n and rows.iloc[start_i]["PERIOD"] != cur_period:
                    cur_period = rows.iloc[start_i]["PERIOD"]
                    poss_idx = 0
                pending_made = None
                last_miss_team = None
                last_control_team = None
                dead_ball_pending = False
                continue
        else:
            if ((action == "free_throw" and _continues_trip(possessions, rows, start_i, i, row,
                                                            team, kind, cur_period))
                    # A same-instant control event by the team that just scored its
                    # FT is still that possession: the opponent cannot have held the
                    # ball at an unchanged clock. A turnover (2025-26 0022501009: FT
                    # 1 of 1 made, then offensive goaltending; the feed's `possession`
                    # shows the same team throughout), or a shot entered after FTs it
                    # preceded -- an and-one's layup (2017-18 0021701053, 2023-24
                    # 0022300072: 'Fox FT 1 of 1 (16 PTS)' then 'Fox Jump Shot (15
                    # PTS)') or the blocked miss before a putback foul (2018-19
                    # 0021800368).
                    or (action in ("turnover", "made_shot", "missed_shot")
                        and _after_own_ft_end(possessions, rows, start_i, i, row, team,
                                              cur_period))):
                # Free-throw trip continuation (checked BEFORE implied change): a later
                # FT of a mislabeled trip (2017-18 0021700001: 'Tatum FT 1 of 1' then
                # '2 of 2' at one ELAPSED) or a new 1-shot award after a same-instant
                # foul (2024-25 0022400105: made FT 2 of 2, loose-ball foul, 'Free
                # Throw 1 of 1' same team). Reopen the possession that closed on the
                # earlier FT and reprocess this one: made final keeps it closed here;
                # missed final leaves it live, and the ensuing rebound decides.
                prev = possessions.pop()
                start_i = prev["START_SEQ"]
                poss_idx = prev["POSS_IDX"]
                continue
            is_control_event = (action in ("made_shot", "missed_shot", "turnover")
                                or (action == "free_throw" and kind == "regular"))
            # Until the new possession shows its own control event, the team that
            # gained the ball from the previous terminal event (opponent after a
            # score/turnover, the rebounder after a defensive rebound) is in control:
            # a jump ball lost after a coach's challenge (2022-23 0022200567) or an
            # unlogged opponent possession after a made shot (0022200534) then
            # surfaces as an implied change instead of merging two teams.
            controller = last_control_team
            if controller is None and start_i < i:
                controller = _control_after(possessions, cur_period)
            if (is_control_event and controller is not None and team is not None
                    and team != controller):
                # Implied possession change: no explicit closing event (often a
                # missing rebound row) separates the old possession's last event
                # from this new-team control event. Close the old one at the
                # immediately preceding event and start fresh here (2017-18
                # 0021700002: MISS McCaw layup -> Gordon Step Out of Bounds
                # Turnover, no rebound row between). Technical/flagrant/clear-path
                # free throws and rebounds never reach this branch (excluded by
                # the outer condition / handled by their own rules).
                _append_possession(possessions, gid, cur_period, poss_idx, start_i, i - 1,
                                    "implied_change", controller, rows, home_t, away_t)
                poss_idx += 1
                start_i = i
                last_miss_team = None
                last_control_team = None
                dead_ball_pending = False
                if rows.iloc[start_i]["PERIOD"] != cur_period:
                    cur_period = rows.iloc[start_i]["PERIOD"]
                    poss_idx = 0
                continue
            if action == "made_shot":
                pending_made = (i, team)
                last_control_team = team
                i += 1
                continue
            elif action == "missed_shot":
                last_miss_team = team
                last_control_team = team
                i += 1
                continue
            elif action == "free_throw":
                num, of_ = _v(row["FT_NUM"]), _v(row["FT_OF"])
                if kind != "technical":
                    last_control_team = team
                if kind == "regular":
                    is_final = num is not None and of_ is not None and num == of_
                    made = _v(row["FT_MADE"])
                    if is_final:
                        if made:
                            terminal = True
                            outcome = "free_throw_made"
                            offense_team = team
                        else:
                            last_miss_team = team
                    else:
                        if made is False:
                            dead_ball_pending = True
                if not terminal:
                    i += 1
                    continue
            elif action == "rebound":
                if dead_ball_pending:
                    dead_ball_pending = False
                    i += 1
                    continue
                if team is None or last_miss_team is None:
                    i += 1
                    continue
                if _same_team(team, last_miss_team):
                    # An offensive rebound keeps the shooting team: do NOT clear the
                    # miss. The feed can order a same-clock tip miss before the
                    # offensive rebound of the first miss (2015-16 0021500069); the
                    # next rebound by the other team must still end this possession.
                    last_control_team = team
                    i += 1
                    continue
                terminal = True
                outcome = "defensive_rebound"
                offense_team = last_miss_team
            elif action == "turnover":
                terminal = True
                outcome = "turnover"
                offense_team = team
            elif action == "period":
                if bool(row["PERIOD_END"]):
                    if start_i == i and possessions:
                        # Nothing has been accumulated since the previous close: fold
                        # this boundary marker into that possession rather than
                        # opening a new, event-only possession with unknown offense
                        # ("an empty trailing segment with no events is not a
                        # possession").
                        last = possessions[-1]
                        last["END_SEQ"] = int(row["SEQ"])
                        last["HOME_PTS"] += float(row["PTS_HOME"])
                        last["AWAY_PTS"] += float(row["PTS_AWAY"])
                        i = _fold_period_tail(possessions, rows, i, cur_period)
                        start_i = i + 1
                        last_miss_team = None
                        last_control_team = None
                        dead_ball_pending = False
                        i += 1
                        if start_i < n and rows.iloc[start_i]["PERIOD"] != cur_period:
                            cur_period = rows.iloc[start_i]["PERIOD"]
                            poss_idx = 0
                        continue
                    terminal = True
                    outcome = "end_of_period"
                    offense_team = last_control_team
                    if offense_team is None:
                        offense_team = _control_after(possessions, cur_period)
                else:
                    i += 1
                    continue
            else:
                i += 1
                continue

        if terminal:
            _append_possession(possessions, gid, cur_period, poss_idx, start_i, i,
                                outcome, offense_team, rows, home_t, away_t)
            poss_idx += 1
            if outcome == "end_of_period":
                i = _fold_period_tail(possessions, rows, i, cur_period)
            start_i = i + 1
            last_miss_team = None
            last_control_team = None
            dead_ball_pending = False
            i += 1
            if start_i < n and rows.iloc[start_i]["PERIOD"] != cur_period:
                cur_period = rows.iloc[start_i]["PERIOD"]
                poss_idx = 0
            continue

    if pending_made is not None:
        p_idx, p_team = pending_made
        _append_possession(possessions, gid, cur_period, poss_idx, start_i, p_idx,
                            "made_shot", p_team, rows, home_t, away_t)
        start_i = p_idx + 1

    if start_i < n:
        # Events ordered after the true close of the game (e.g. an administrative
        # Instant Replay / Support Ruling row trailing the final period-end) must
        # still tile into exactly one possession: fold them into the last one
        # rather than opening a new possession for them.
        tail = rows.iloc[start_i:n]
        if possessions:
            last = possessions[-1]
            last["END_SEQ"] = int(rows.iloc[n - 1]["SEQ"])
            last["HOME_PTS"] += float(tail["PTS_HOME"].sum())
            last["AWAY_PTS"] += float(tail["PTS_AWAY"].sum())
        else:
            _append_possession(possessions, gid, cur_period, poss_idx, start_i, n - 1,
                                "end_of_period", None, rows, home_t, away_t)

    return possessions


def _segments_for_possession(rows: pd.DataFrame, poss: dict, home_t) -> list:
    s, e = poss["START_SEQ"], poss["END_SEQ"]
    sub = rows.iloc[s:e + 1]
    key = list(zip(sub["HOME_ON"], sub["AWAY_ON"], sub["LINEUP_VALID"]))
    offense_is_home = None if poss["OFFENSE_TEAM_ID"] is None else bool(poss["OFFENSE_TEAM_ID"] == home_t)
    segs = []
    seg_idx = 0
    start = 0
    m = len(key)
    for j in range(1, m + 1):
        if j == m or key[j] != key[start]:
            seg_rows = sub.iloc[start:j]
            home_on, away_on, valid = key[start]
            segs.append({
                "GAME_ID": poss["GAME_ID"], "PERIOD": poss["PERIOD"], "POSS_IDX": poss["POSS_IDX"],
                "SEG_IDX": seg_idx,
                "HOME_ON": home_on, "AWAY_ON": away_on, "LINEUP_VALID": valid,
                "HOME_PTS": float(seg_rows["PTS_HOME"].sum()), "AWAY_PTS": float(seg_rows["PTS_AWAY"].sum()),
                "POSS_COUNT": 1 if j == m else 0,
                "OFFENSE_IS_HOME": offense_is_home,
            })
            seg_idx += 1
            start = j
    return segs


def reconstruct_possessions(norm: pd.DataFrame):
    """Call only on ADMITTED games. Tiles every event of a game/period into
    exactly one possession, then splits each possession into lineup segments."""
    n = norm.sort_values(["GAME_ID", "SEQ"], kind="mergesort")
    all_poss, all_segs = [], []
    for gid, g in n.groupby("GAME_ID", sort=False):
        g = g.reset_index(drop=True)
        poss_list = _reconstruct_game(g)
        home_t = g["HOME_TEAM_ID"].iloc[0]
        all_poss.extend(poss_list)
        for p in poss_list:
            all_segs.extend(_segments_for_possession(g, p, home_t))

    possessions = pd.DataFrame(all_poss, columns=[
        "GAME_ID", "PERIOD", "POSS_IDX", "START_SEQ", "END_SEQ", "OUTCOME",
        "OFFENSE_TEAM_ID", "DEFENSE_TEAM_ID", "HOME_PTS", "AWAY_PTS",
    ])
    if len(possessions):
        possessions["OFFENSE_TEAM_ID"] = possessions["OFFENSE_TEAM_ID"].astype("Int64")
        possessions["DEFENSE_TEAM_ID"] = possessions["DEFENSE_TEAM_ID"].astype("Int64")
    segments = pd.DataFrame(all_segs, columns=[
        "GAME_ID", "PERIOD", "POSS_IDX", "SEG_IDX", "HOME_ON", "AWAY_ON", "LINEUP_VALID",
        "HOME_PTS", "AWAY_PTS", "POSS_COUNT", "OFFENSE_IS_HOME",
    ])
    return possessions, segments


def build_stints(segments: pd.DataFrame, game_teams: pd.DataFrame, season: str):
    """Aggregate VALID segments into the incumbent stint schema (no min-possession
    filter -- the fit config applies that). `exclusions`: exposure/score dropped
    per game because the segment's lineup was invalid."""
    gt = game_teams.copy()
    gt["GAME_ID"] = _gid(gt["GAME_ID"])
    gt = gt.set_index("GAME_ID")

    valid = segments[segments["LINEUP_VALID"]].copy()
    grouped = valid.groupby(["GAME_ID", "HOME_ON", "AWAY_ON"], sort=False).agg(
        home_points=("HOME_PTS", "sum"), away_points=("AWAY_PTS", "sum"),
        possessions=("POSS_COUNT", "sum"),
    ).reset_index()
    grouped["net_points"] = grouped["home_points"] - grouped["away_points"]
    grouped["net_rating_per_100"] = np.where(
        grouped["possessions"] > 0, grouped["net_points"] / grouped["possessions"] * 100.0, np.nan)
    grouped["home_team_id"] = grouped["GAME_ID"].map(gt["HOME_TEAM_ID"])
    grouped["away_team_id"] = grouped["GAME_ID"].map(gt["AWAY_TEAM_ID"])
    grouped["season"] = season
    grouped["home_lineup"] = grouped["HOME_ON"].map(list)
    grouped["away_lineup"] = grouped["AWAY_ON"].map(list)
    grouped["game_id"] = grouped["GAME_ID"]
    stints = grouped[[
        "game_id", "home_lineup", "away_lineup", "home_team_id", "away_team_id",
        "home_points", "away_points", "net_points", "possessions", "net_rating_per_100", "season",
    ]].reset_index(drop=True)

    invalid = segments[~segments["LINEUP_VALID"]]
    if len(invalid):
        exclusions = invalid.groupby("GAME_ID", sort=False).agg(
            EXCLUDED_POSS=("POSS_COUNT", "sum"),
            EXCLUDED_HOME_PTS=("HOME_PTS", "sum"),
            EXCLUDED_AWAY_PTS=("AWAY_PTS", "sum"),
        ).reset_index()
    else:
        exclusions = pd.DataFrame(columns=["GAME_ID", "EXCLUDED_POSS", "EXCLUDED_HOME_PTS", "EXCLUDED_AWAY_PTS"])
    return stints, exclusions


def game_accounting_rows(possessions: pd.DataFrame, game_teams: pd.DataFrame, box: pd.DataFrame,
                          periods, season: str) -> pd.DataFrame:
    """Rows in the exact `GAME_ACCOUNTING_COLUMNS` shape consumed by
    `audit_rapm_exposure_units.game_accounting`."""
    gt = game_teams.copy()
    gt["GAME_ID"] = _gid(gt["GAME_ID"])
    box_idx = box.copy()
    box_idx["GAME_ID"] = _gid(box_idx["GAME_ID"])
    box_idx = box_idx.set_index("GAME_ID")

    rows = []
    for _, gr in gt.iterrows():
        gid = gr["GAME_ID"]
        h, a = gr["HOME_TEAM_ID"], gr["AWAY_TEAM_ID"]
        team_a, team_b = sorted([h, a])
        pg = possessions[possessions["GAME_ID"] == gid]
        home_pts = float(pg["HOME_PTS"].sum())
        away_pts = float(pg["AWAY_PTS"].sum())
        pbp_a, pbp_b = (home_pts, away_pts) if h == team_a else (away_pts, home_pts)
        if gid in box_idx.index:
            box_home = float(box_idx.loc[gid, "HOME_PTS"])
            box_away = float(box_idx.loc[gid, "AWAY_PTS"])
            box_a, box_b = (box_home, box_away) if h == team_a else (box_away, box_home)
        else:
            box_a = box_b = np.nan
        poss_a = int((pg["OFFENSE_TEAM_ID"] == team_a).sum())
        poss_b = int((pg["OFFENSE_TEAM_ID"] == team_b).sum())
        unattributed_poss = int(pg["OFFENSE_TEAM_ID"].isna().sum())
        per = periods.get(gid, np.nan) if hasattr(periods, "get") else np.nan
        rows.append({
            "GAME_ID": gid, "SEASON_ID": season, "PERIODS": per,
            "PBP_PTS_A": pbp_a, "PBP_PTS_B": pbp_b, "BOX_PTS_A": box_a, "BOX_PTS_B": box_b,
            "POSS_A": poss_a, "POSS_B": poss_b,
            "UNATTRIBUTED_POSS": unattributed_poss, "UNATTRIBUTED_PTS": 0.0,
        })
    return pd.DataFrame(rows, columns=GAME_ACCOUNTING_COLUMNS)
