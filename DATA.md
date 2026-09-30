# Data

## Two layers

| Layer | Where | What it is | Needed for |
|---|---|---|---|
| **Evaluation tables** | `data/` | One row per game (10,466 games, 2016-17 to 2024-25): the target, each forecast's player component, and cohort flags. Plus `frozen_parameters.json` and `expected.json`. | `reproduce.py`: every number in the abstract, in about a second |
| **Source data** | `source_data/` (git submodule) | The NBA.com play-by-play and game data, and our derived runs, from which the tables are built. See `source_data/README.md`. | `rebuild_tables.py`: regenerates `data/*.csv` from the source and requires an exact match |

The submodule shows where the numbers came from. Nobody has to fetch it to check the paper's results.

## Evaluation tables (`data/`)

Columns:
- `GAME_ID`, `SEASON`, `GAME_DATE`, `PHASE` (development or holdout), `EVAL_ORDER` (the evaluation's row order; the bootstrap draws depend on it).
- `ACTUAL`: the home team's net points per 100 combined (both-team) possessions, from reconciled possession accounting.
- `WEIGHT`: possessions in the game.
- `PLAYER_PART_<model>`: each forecast's player component, before the frozen offset `h` is added.
- `RATED_SHARE_<model>`: the share of possessions played by players the model rated.
- Cohort flags: `MATCHED`, `EARLY_SEASON`, `ROOKIE_HEAVY`, `TEAM_CHANGE`, `ROOKIE_SHARE`.

8,017 development games (2016-17 to 2022-23) and 2,430 holdout games (2023-24 and 2024-25) are matched across all four forecasts. The other 19 rows are unmatched and are not scored. The tables contain no player identities, events or box scores.

## Source data (`source_data/`)

- **Source: NBA.com.** Statistics courtesy of NBA.com. The submodule holds NBA.com play-by-play (unmodified) and game data for 2015-16 to 2024-25, plus derived runs (reconciled possessions, stints and the rating fits).
- **Terms.** NBA.com's Terms of Use, section 9 ("NBA Statistics"), limit use, display or publication of NBA statistics to legitimate news reporting or private, non-commercial purposes, with prominent attribution to NBA.com. The authors publish this as a fixed, non-commercial research artifact for an academic conference submission. It is not a regularly updated statistics database. Anyone reusing the data is responsible for their own compliance. This is not legal advice.
- **Not included.** Basketball-Reference data, and every table the evaluation does not read. See `source_data/README.md`.
- **Pinned.** The submodule is pinned to a specific commit; the tag `ssac27-abstract-v1` marks the version as submitted.

## Rebuilding from source

```bash
git submodule update --init            # about 250 MB
pip install -r requirements.txt -r requirements-rebuild.txt
python rebuild_tables.py               # about a minute
```

`rebuild_tables.py` runs the code in `pipeline/` (the evaluation code exactly as of commit `e3140577b`). It checks the sha256 of every input the season manifests seal (the team game table, the rotation stints, and every play-by-play file) and refuses on any mismatch. It then rebuilds both tables and requires every column to equal `data/*.csv` to 1e-9.

This step regenerates the evaluation tables from the source data. It does not refit the ratings from raw play-by-play: the fitted runs are inputs in `source_data/runs/`, and the code that produced them (the possession builder and ridge fits) is in `pipeline/` for inspection.
