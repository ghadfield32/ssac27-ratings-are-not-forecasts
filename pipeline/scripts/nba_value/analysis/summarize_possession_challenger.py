"""D1b — summarize possession challenger release runs across seasons.

For each season directory under --root (<season>/release/<RUN_ID>/), report the
release status, admitted / quarantined games by reason, declared exclusions by
reason and policy, every blocking game by id, possessions per admitted game, and the
per-game ratio of challenger possessions to both teams' box possessions next to
the incumbent's row coverage from the committed D1 audit. The independent gate
(validate_possession_challenger.run_checks) is re-run on every release run.

Writes reports/nba_value/player_impact_value/d1b_possession_challenger.{json,md}.

Usage:
  python scripts/nba_value/analysis/summarize_possession_challenger.py --root <scratch>/d1b/v2
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api.src.ml.io.atomic_io import write_json_atomic
from scripts.nba_value.analysis.audit_rapm_exposure_units import EXCLUDABLE_REASONS
from scripts.nba_value.validation.validate_possession_challenger import run_checks

DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"
OUT_DIR = PROJECT_ROOT / "reports" / "nba_value" / "player_impact_value"
AUDIT_JSON = OUT_DIR / "d1_rapm_exposure_audit.json"


def box_possessions(data_root: Path) -> pd.Series:
    tg = pd.read_parquet(data_root / "silver/nba/facts/team_game_fact.parquet",
                         columns=["GAME_ID", "FGA", "FTA", "OREB", "TOV"])
    tg["GAME_ID"] = tg["GAME_ID"].astype(str).str.zfill(10)
    tg["P"] = tg["FGA"] + 0.44 * tg["FTA"] - tg["OREB"] + tg["TOV"]
    g = tg.groupby("GAME_ID")["P"].agg(["sum", "count"])
    return g.loc[g["count"] == 2, "sum"]


def season_summary(run_dir: Path, box_poss: pd.Series, incumbent: dict) -> dict:
    m = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    status = pd.read_parquet(run_dir / "game_status.parquet")
    poss = pd.read_parquet(run_dir / "possessions.parquet")
    per_game = poss.groupby("GAME_ID").size()
    ratio = (per_game / box_poss.reindex(per_game.index)).dropna()
    q = status[status["STATUS"] != "ADMITTED"]
    blocking = q[~q["REASON"].isin(EXCLUDABLE_REASONS)]
    declared = q[q["GAME_ID"].isin(m["release"]["excluded"])]
    checks = run_checks(run_dir)
    release = m["release"]
    gate_failures = [n for n, ok, _ in checks if not ok]
    return {
        "season": m["season"], "run_id": m["run_id"], "release_status": release["status"],
        # Releasable only when the release predicate AND the independent gate agree:
        # the gate's per-period alternation check is stricter than the predicate.
        "releasable": release["status"] in ("PASS", "PASS_WITH_EXCLUSIONS") and not gate_failures,
        "gate": f"{sum(ok for _, ok, _ in checks)}/{len(checks)}",
        "gate_failures": gate_failures,
        "cohort_games": m["games"]["cohort"], "admitted": m["games"]["admitted"],
        "exclusion_policies": m["exclusion_policies"],
        "declared_exclusions": release["excluded_games"],
        "declared_exclusions_by_reason": declared["REASON"].value_counts().sort_index().to_dict(),
        # Non-excludable quarantines (wrong data, unexplained alternation): each blocks its season.
        "blocking_games": {g: r for g, r in zip(blocking["GAME_ID"], blocking["REASON"])},
        "quarantine_reasons": m["quarantine_reasons"],
        "attribution_incomplete_admitted": int(poss["OFFENSE_TEAM_ID"].isna().sum()),
        # Within the alternation bound, so admitted; diagnostic only.
        "admitted_same_team_repeats": int(status.loc[status["STATUS"] == "ADMITTED", "SAME_TEAM_REPEATS"].sum()),
        "admitted_verified_unlogged": int(status.loc[status["STATUS"] == "ADMITTED",
                                                     "UNLOGGED_POSSESSION_GAPS"].sum()),
        "alternation_violations": release["alternation_violations"],
        "possessions": m["possessions"],
        "possessions_per_admitted_game": round(m["possessions"] / max(m["games"]["admitted"], 1), 1),
        "median_challenger_poss_over_box_poss": round(float(ratio.median()), 3),
        "incumbent_rows_over_box_poss": incumbent.get(m["season"]),
        "invalid_lineup_possessions_excluded": m["excluded_possessions"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    incumbent = {r["season"]: round(r["median_rows_over_box_poss"], 3)
                 for r in audit["season_coverage"] if r.get("status") == "MEASURED"}
    box_poss = box_possessions(args.data_root)
    rows = []
    for season_dir in sorted(p for p in args.root.iterdir() if p.is_dir()):
        runs = [p for p in (season_dir / "release").iterdir() if p.is_dir() and not p.name.startswith(".")]
        if len(runs) != 1:
            raise RuntimeError(f"{season_dir}: expected exactly one release run, found {[r.name for r in runs]}")
        rows.append(season_summary(runs[0], box_poss, incumbent))
    report = {"report": "D1b possession challenger", "generated_at_utc": datetime.now(UTC).isoformat(),
              "root": str(args.root), "seasons": rows,
              "all_seasons_releasable": all(r["releasable"] for r in rows)}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(report, args.out_dir / "d1b_possession_challenger.json", indent=2)
    cols = ["season", "releasable", "release_status", "gate", "gate_failures", "cohort_games", "admitted",
            "declared_exclusions_by_reason", "alternation_violations",
            "admitted_same_team_repeats", "admitted_verified_unlogged",
            "possessions_per_admitted_game", "median_challenger_poss_over_box_poss",
            "incumbent_rows_over_box_poss", "invalid_lineup_possessions_excluded"]
    df = pd.DataFrame(rows)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    blocking = [f"- {r['season']}: " + ", ".join(f"`{g}` ({why})" for g, why in r["blocking_games"].items())
                for r in rows if r["blocking_games"]]
    md = ["# D1b — possession challenger across seasons", "",
          f"Generated {report['generated_at_utc']} by `scripts/nba_value/analysis/summarize_possession_challenger.py`.",
          "", f"All seasons releasable: **{report['all_seasons_releasable']}**", "", *lines, "",
          "## Blocking games (never excludable; each blocks its season)", "",
          *(blocking or ["- none"]), "",
          f"Total blocking games: {int(df['blocking_games'].map(len).sum())}", ""]
    (args.out_dir / "d1b_possession_challenger.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
