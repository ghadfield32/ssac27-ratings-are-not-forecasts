# Data

## What this repository contains

| File | Rows | What it is |
|---|---:|---|
| `data/pmi_games_track_b.csv` | 10,466 games | Per-game evaluation table, **projected participation** (the operational pregame track) |
| `data/pmi_games_track_a.csv` | 10,466 games | The same games with **observed participation** (diagnostic track) |
| `data/frozen_parameters.json` | — | Per-model offset `h` and residual quantiles, fitted on development games only and frozen before the holdout was read |
| `data/expected.json` | — | The committed evaluation results that `reproduce.py` checks against |

The tables cover 2016-17 to 2024-25 NBA regular-season games: 8,017 development games (2016-17 to 2022-23) and 2,430 holdout games (2023-24 and 2024-25) that are matched across all four forecasts. The other 19 rows are unmatched and are not scored.

Columns:
- `GAME_ID`, `SEASON`, `GAME_DATE`, `PHASE` (development or holdout), `EVAL_ORDER` (the evaluation's row order; the bootstrap draws depend on it).
- `ACTUAL`: the home team's net points per 100 combined (both-team) possessions, from reconciled possession accounting.
- `WEIGHT`: possessions in the game.
- `PLAYER_PART_<model>`: each forecast's player component, before the frozen offset `h` is added.
- `RATED_SHARE_<model>`: the share of possessions played by players the model rated.
- Cohort flags: `MATCHED`, `EARLY_SEASON`, `ROOKIE_HEAVY`, `TEAM_CHANGE`, `ROOKIE_SHARE`.

These two tables are **sufficient to regenerate every number in the abstract**: RMSEs, paired bootstrap intervals, calibration slopes, interval coverage and the post hoc development-only rescaling. They contain no player identities, no play-by-play events and no box scores.

## Source and attribution

**Source: NBA.com.** The game results and play-by-play from which these per-game values were derived come from NBA.com statistics. Attribution: **statistics courtesy of NBA.com**.

The NBA.com Terms of Use (section 9, "NBA Statistics") allow statistics to be "used, displayed, or published for legitimate news reporting or private, non-commercial purposes", with prominent attribution. They also say statistics may not be used "in connection with any website... that features a database... of comprehensive, regularly updated statistics" without consent.

This repository is a fixed, non-commercial research artifact for an academic conference submission. It is not a regularly updated statistics database, and it publishes derived per-game model evaluation values only. It is not legal advice; the authors are responsible for their use of third-party data.

## What is deliberately NOT included, and how to regenerate it

- **Raw play-by-play, box scores and rotation data.** These are NBA.com content and are not redistributed here.
- **Player-level ratings and stint-level possession data.** These are derived from the above. They are needed only to *refit* the ratings, not to reproduce the evaluation.

`pipeline/` contains the exact code, as of the evaluation commit, that built the possession ledger, fitted the ratings and produced these tables. A reader who wants to refit end to end fetches the same public NBA.com play-by-play, for game IDs listed in the CSVs, with any standard client, and runs that code. That path is documented but not required to check the paper's numbers.
