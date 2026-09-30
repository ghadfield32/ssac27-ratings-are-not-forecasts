"""Blocking gate for a D1b possession challenger run. Exit 0 = PASS.

Independent of the writer: every check is re-derived in DuckDB SQL from the run's
parquet outputs and the raw box record (it shares no code with possession_ledger or
the audit predicate), after re-hashing the run files and the sealed inputs.

Usage:
  python scripts/nba_value/validation/validate_possession_challenger.py --run-dir <dir>
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count(con, sql: str, **params) -> int:
    return int(con.execute(sql, params).fetchone()[0])


def run_checks(run_dir: Path) -> list[tuple[str, bool, str]]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    bad = [n for n, h in manifest["files"].items() if _sha(run_dir / n) != h]
    check("manifest_file_hashes", not bad, f"mismatch={bad}")
    check("run_id_consistent", run_dir.name == manifest["run_id"])
    drift = [k for k, v in manifest["inputs"].items()
             if not Path(v["path"]).exists() or _sha(Path(v["path"])) != v["sha256"]]
    check("sealed_inputs_unchanged", not drift, f"drifted={drift}")

    con = duckdb.connect()
    for name in ("game_status", "possessions", "segments", "stints", "exclusions",
                 "excluded_possessions", "excluded_events"):
        literal = str(run_dir / f"{name}.parquet").replace("'", "''")   # views cannot bind params
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{literal}')")
    con.execute("""CREATE VIEW admitted AS SELECT GAME_ID FROM game_status WHERE STATUS = 'ADMITTED'""")

    cohort = set(manifest["cohort"])
    status_ids = {r[0] for r in con.execute("SELECT GAME_ID FROM game_status").fetchall()}
    check("every_cohort_game_has_a_status", status_ids == cohort,
          f"missing={sorted(cohort - status_ids)[:5]} extra={sorted(status_ids - cohort)[:5]}")
    check("quarantine_has_reason", _count(con, """SELECT count(*) FROM game_status
          WHERE STATUS <> 'ADMITTED' AND (REASON IS NULL OR REASON = '')""") == 0)
    check("only_admitted_games_reconstructed", _count(con, """SELECT count(*) FROM possessions
          WHERE GAME_ID NOT IN (SELECT GAME_ID FROM admitted)""") == 0)

    # Possessions tile each game: each starts one event after the previous one ends.
    gaps = _count(con, """SELECT count(*) FROM (
        SELECT START_SEQ, lag(END_SEQ) OVER (PARTITION BY GAME_ID ORDER BY START_SEQ) AS prev_end
        FROM possessions) WHERE prev_end IS NOT NULL AND START_SEQ <> prev_end + 1""")
    check("possessions_tile_each_game", gaps == 0, f"gaps={gaps}")

    # Points per real home/away side against the raw box record (TEAM vs. OPP = home).
    tg = manifest["inputs"]["team_game_fact"]["path"]
    unreconciled = _count(con, """
        WITH box AS (
            SELECT lpad(CAST(GAME_ID AS VARCHAR), 10, '0') AS gid,
                   sum(CASE WHEN MATCHUP LIKE '% vs. %' THEN PTS END) AS home_pts,
                   sum(CASE WHEN MATCHUP LIKE '% @ %' THEN PTS END) AS away_pts
            FROM read_parquet($tg) GROUP BY 1),
        pbp AS (SELECT GAME_ID, sum(HOME_PTS) AS h, sum(AWAY_PTS) AS a FROM possessions GROUP BY 1)
        SELECT count(*) FROM admitted ad LEFT JOIN pbp ON pbp.GAME_ID = ad.GAME_ID
        LEFT JOIN box ON box.gid = ad.GAME_ID
        WHERE pbp.h IS DISTINCT FROM box.home_pts OR pbp.a IS DISTINCT FROM box.away_pts""", tg=tg)
    check("admitted_points_equal_box_by_side", unreconciled == 0, f"games={unreconciled}")

    seg_mismatch = _count(con, """
        WITH s AS (SELECT GAME_ID, PERIOD, POSS_IDX, sum(HOME_PTS) h, sum(AWAY_PTS) a, sum(POSS_COUNT) c
                   FROM segments GROUP BY ALL)
        SELECT count(*) FROM possessions p FULL OUTER JOIN s
            ON s.GAME_ID = p.GAME_ID AND s.PERIOD = p.PERIOD AND s.POSS_IDX = p.POSS_IDX
        WHERE p.GAME_ID IS NULL OR s.GAME_ID IS NULL
           OR s.h <> p.HOME_PTS OR s.a <> p.AWAY_PTS OR s.c <> 1""")
    check("segments_sum_to_possessions", seg_mismatch == 0, f"mismatch={seg_mismatch}")

    stint_gap = _count(con, """
        WITH seg AS (SELECT GAME_ID, sum(POSS_COUNT) c, sum(HOME_PTS) h, sum(AWAY_PTS) a FROM segments GROUP BY 1),
             st AS (SELECT game_id AS GAME_ID, sum(possessions) c, sum(home_points) h, sum(away_points) a
                    FROM stints GROUP BY 1),
             ex AS (SELECT GAME_ID, sum(EXCLUDED_POSS) c, sum(EXCLUDED_HOME_PTS) h, sum(EXCLUDED_AWAY_PTS) a
                    FROM exclusions GROUP BY 1)
        SELECT count(*) FROM seg LEFT JOIN st USING (GAME_ID) LEFT JOIN ex USING (GAME_ID)
        WHERE seg.c <> coalesce(st.c, 0) + coalesce(ex.c, 0)
           OR seg.h <> coalesce(st.h, 0) + coalesce(ex.h, 0)
           OR seg.a <> coalesce(st.a, 0) + coalesce(ex.a, 0)""")
    check("stints_plus_exclusions_equal_segments", stint_gap == 0, f"games={stint_gap}")
    check("stint_rates_finite_or_nan", _count(con, """SELECT count(*) FROM stints
          WHERE isinf(net_rating_per_100) OR (possessions = 0 AND net_rating_per_100 IS NOT NULL
          AND NOT isnan(net_rating_per_100))""") == 0)

    unattributed = _count(con, "SELECT count(*) FROM possessions WHERE OFFENSE_TEAM_ID IS NULL")
    check("every_possession_attributed", unattributed == 0, f"unattributed={unattributed}")
    alternation = _count(con, """
        WITH per AS (SELECT GAME_ID, count(DISTINCT PERIOD) periods,
                     count(*) FILTER (WHERE OFFENSE_TEAM_ID = (SELECT min(OFFENSE_TEAM_ID) FROM possessions q
                                                               WHERE q.GAME_ID = p.GAME_ID)) na,
                     count(*) FILTER (WHERE OFFENSE_TEAM_ID <> (SELECT min(OFFENSE_TEAM_ID) FROM possessions q
                                                                WHERE q.GAME_ID = p.GAME_ID)) nb
                     FROM possessions p GROUP BY 1)
        SELECT count(*) FROM per WHERE abs(na - nb) > periods""")
    check("possession_alternation_within_periods", alternation == 0, f"games={alternation}")
    # Stricter: inside one period possessions alternate, so the two teams' counts
    # differ by at most one in every period (a gap of 2+ is a missing boundary).
    per_period = _count(con, """
        WITH t AS (SELECT DISTINCT GAME_ID, OFFENSE_TEAM_ID FROM possessions WHERE OFFENSE_TEAM_ID IS NOT NULL),
             teams AS (SELECT GAME_ID, min(OFFENSE_TEAM_ID) a, max(OFFENSE_TEAM_ID) b FROM t GROUP BY 1),
             per AS (SELECT p.GAME_ID, p.PERIOD,
                            count(*) FILTER (WHERE p.OFFENSE_TEAM_ID = teams.a) na,
                            count(*) FILTER (WHERE p.OFFENSE_TEAM_ID = teams.b) nb
                     FROM possessions p JOIN teams USING (GAME_ID) GROUP BY 1, 2)
        SELECT count(DISTINCT GAME_ID) FROM per WHERE abs(na - nb) > 1""")
    check("possession_alternation_per_period", per_period == 0, f"games={per_period}")
    release = manifest["release"]
    check("release_status_recorded", release["status"] in ("PASS", "PASS_WITH_EXCLUSIONS", "FAIL"),
          release["status"])
    # Re-check every accepted exclusion against the run's own status table: only a
    # source-absence reason, and only the reason the game was actually quarantined for.
    reasons = dict(con.execute("SELECT GAME_ID, REASON FROM game_status").fetchall())
    bad_excl = [g for g in release.get("excluded", [])
                if reasons.get(g) not in ("no_bronze_pbp", "link_empty", "no_events_in_source",
                                          "source_order_unresolvable", "source_possession_unlogged")
                or manifest["declared_exclusions"][g]["declared"] != reasons.get(g)]
    check("exclusions_are_declared_and_excludable", not bad_excl, f"bad={bad_excl[:5]}")
    # Policy source-order-v1, re-checked from the sealed game_status evidence: an
    # ordering exclusion must have exact scoring (final == box by side, nothing
    # unresolved), order-inversion evidence, the legacy feed, and no trace left in
    # the model inputs.
    order_bad = _count(con, """
        SELECT count(*) FROM game_status gs
        WHERE gs.REASON = 'source_order_unresolvable'
          AND (gs.FINAL_HOME IS DISTINCT FROM gs.BOX_HOME OR gs.FINAL_AWAY IS DISTINCT FROM gs.BOX_AWAY
               OR gs.UNRESOLVED_SCORING_EVENTS <> 0 OR coalesce(gs.ORDER_INVERSIONS, 0) = 0
               OR gs.EVENT_SCHEMA <> 'legacy'
               OR gs.GAME_ID IN (SELECT GAME_ID FROM possessions)
               OR gs.GAME_ID IN (SELECT GAME_ID FROM segments)
               OR gs.GAME_ID IN (SELECT game_id FROM stints))""")
    check("source_order_exclusions_meet_policy", order_bad == 0, f"games={order_bad}")

    # Every game removed for alternation has its possessions and event rows sealed.
    removed = {r[0] for r in con.execute("""SELECT GAME_ID FROM game_status WHERE REASON IN
        ('source_order_unresolvable', 'source_possession_unlogged', 'possession_alternation_unexplained')""").fetchall()}
    sealed_p = {r[0] for r in con.execute("SELECT DISTINCT GAME_ID FROM excluded_possessions").fetchall()}
    sealed_e = {r[0] for r in con.execute("SELECT DISTINCT GAME_ID FROM excluded_events").fetchall()}
    check("alternation_removals_sealed", removed == sealed_p == sealed_e,
          f"removed={len(removed)} possessions={len(sealed_p)} events={len(sealed_e)}")
    # Policy source-absence-v2, re-derived here from the sealed rows: the game's failing
    # periods (2+ possession gap) are recomputed, and EVERY same-team repeat in them
    # must be an opponent possession absent from the source -- the first possession
    # gave the ball away, the next possession's first row is the same team's control
    # event at a strictly later clock, and both rows' player is on the row's team (or
    # the row is a team event naming it). Scoring must be exact and nothing may reach
    # the model inputs.
    unlogged_bad = _count(con, """
        WITH g AS (SELECT GAME_ID FROM game_status WHERE REASON = 'source_possession_unlogged'),
        ep AS (SELECT * FROM excluded_possessions WHERE GAME_ID IN (SELECT GAME_ID FROM g)),
        teams AS (SELECT GAME_ID, min(OFFENSE_TEAM_ID) a, max(OFFENSE_TEAM_ID) b FROM ep GROUP BY 1),
        per AS (SELECT ep.GAME_ID, ep.PERIOD,
                       count(*) FILTER (WHERE ep.OFFENSE_TEAM_ID = teams.a) na,
                       count(*) FILTER (WHERE ep.OFFENSE_TEAM_ID = teams.b) nb
                FROM ep JOIN teams USING (GAME_ID) GROUP BY 1, 2),
        failing AS (SELECT GAME_ID, PERIOD FROM per WHERE abs(na - nb) > 1),
        seq AS (SELECT GAME_ID, PERIOD, START_SEQ, OFFENSE_TEAM_ID,
                       lag(OFFENSE_TEAM_ID) OVER w AS prev_team, lag(OUTCOME) OVER w AS prev_outcome,
                       lag(END_SEQ) OVER w AS prev_end
                FROM ep WINDOW w AS (PARTITION BY GAME_ID, PERIOD ORDER BY START_SEQ)),
        rep AS (SELECT s.* FROM seq s JOIN failing USING (GAME_ID, PERIOD)
                WHERE s.prev_team = s.OFFENSE_TEAM_ID),
        ok AS (SELECT r.GAME_ID, r.PERIOD, r.START_SEQ,
                      coalesce(r.prev_outcome IN ('made_shot', 'and_one', 'turnover', 'defensive_rebound',
                                                  'free_throw_made')
                               AND n.ACTION IN ('made_shot', 'missed_shot', 'turnover')
                               AND n.TEAM_ID = r.OFFENSE_TEAM_ID
                               AND n.ELAPSED > t.ELAPSED
                               AND (t.PERSON_TEAM_ID = t.TEAM_ID OR t.PERSON_ID = t.TEAM_ID)
                               AND (n.PERSON_TEAM_ID = n.TEAM_ID OR n.PERSON_ID = n.TEAM_ID), false) AS verified
               FROM rep r
               LEFT JOIN excluded_events t ON t.GAME_ID = r.GAME_ID AND t.SEQ = r.prev_end
               LEFT JOIN excluded_events n ON n.GAME_ID = r.GAME_ID AND n.SEQ = r.START_SEQ)
        SELECT count(*) FROM game_status gs
        WHERE gs.REASON = 'source_possession_unlogged'
          AND (gs.FINAL_HOME IS DISTINCT FROM gs.BOX_HOME OR gs.FINAL_AWAY IS DISTINCT FROM gs.BOX_AWAY
               OR gs.UNRESOLVED_SCORING_EVENTS <> 0
               OR gs.GAME_ID NOT IN (SELECT GAME_ID FROM failing)
               OR gs.GAME_ID IN (SELECT GAME_ID FROM ep WHERE OFFENSE_TEAM_ID IS NULL)
               OR gs.GAME_ID IN (SELECT f.GAME_ID FROM failing f WHERE NOT EXISTS
                                 (SELECT 1 FROM rep r WHERE r.GAME_ID = f.GAME_ID AND r.PERIOD = f.PERIOD))
               OR gs.GAME_ID IN (SELECT GAME_ID FROM ok WHERE NOT verified)
               OR gs.GAME_ID IN (SELECT GAME_ID FROM possessions)
               OR gs.GAME_ID IN (SELECT GAME_ID FROM segments)
               OR gs.GAME_ID IN (SELECT game_id FROM stints))""")
    check("source_possession_unlogged_exclusions_meet_policy", unlogged_bad == 0, f"games={unlogged_bad}")
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    args = ap.parse_args()
    checks = run_checks(args.run_dir)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
    failed = [c for c in checks if not c[1]]
    print(f"{len(checks) - len(failed)}/{len(checks)} PASS  run={args.run_dir.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
