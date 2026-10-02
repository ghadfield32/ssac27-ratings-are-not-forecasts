# Data, provenance and reproduction boundary

Statistics underlying this study originate from **NBA.com**. The tracked evaluation tables and predictions are derived research artifacts. Attribution is not permission: the MIT licence covers original code only and does not license third-party data. See [RIGHTS.md](RIGHTS.md).

## Publicly tracked evaluation inputs

| Input | Purpose | Public-package state |
|---|---|---|
| `data/pmi_games_track_a.csv` | Actual-participation diagnostic evaluation | Tracked derived table, 10,466 rows |
| `data/pmi_games_track_b.csv` | Projected-participation operational evaluation | Tracked derived table, 10,466 rows |
| `data/frozen_parameters.json` | Development-frozen offsets/residual quantiles | Tracked derived numeric parameters |
| `data/expected.json` | Frozen result checks and previous recalibration values | Tracked derived summary values |

Raw play-by-play, rotations, lineup stints, bulk box scores, player-level provider tables, private fitted-run archives, and credentials are **not** bundled.

The public L1 reproduction binds these four tracked inputs by SHA-256 before running. Exact bindings are recorded in `input_bindings.json` and the reviewed supplement.

## Units and columns

`ACTUAL` is 100 times home-minus-away credited points divided by combined home-and-away reconciled possession counts. It is not the usual per-100-one-team-possession net rating or raw point margin. `PLAYER_PART_<model> + h` is the frozen forecast in that unit.

`GAME_ID` is a string preserving leading zeros. `PHASE` identifies development or holdout, `EVAL_ORDER` preserves original row order, and `MATCHED` identifies the common scoring population. Missing predictions in unmatched rows remain missing; missing values in matched rows refuse analysis.

**`WEIGHT` is track-specific.** Track A contains observed combined stint possessions. Track B is 480, representing two teams' 240 projected minutes; it is not a possession count. The pooled RMSE is game-weighted, not possession-weighted.

There are 8,017 matched development and 2,430 matched holdout games per track. Track B also has 19 unmatched rows: 15 development and 4 holdout. These CSV-row exclusions are distinct from upstream source exclusions and no-valid-lineup gaps.

`EARLY_SEASON`, `ROOKIE_HEAVY`, and `TEAM_CHANGE` are descriptive strata, not issuance-time routing rules. They do not prove externally timestamped historical availability.

## Upstream exclusions

The executed possession release policy admits named source-absence and source-order exclusions, 8–61 per season. In 2024-25, all eight excluded games are source-order exclusions rather than missing play-by-play. Other unratified failures fail the season. Equality of credited and box points checks scoring accounting; it does not prove physical-possession measurement is perfect.

## Three reproduction claims

1. **L1 — saved forecasts to reported statistics: executed publicly.** Anonymous clone reproduction from this repository passed and is recorded in `REPRODUCTION_RECEIPT.json`.
2. **L2 — archived fitted runs to evaluation tables: executed locally.** A separate retained source checkout reconstructed both 10,466-row/20-column tables to tolerance 1e-9. See `LOCAL_SOURCE_RECONSTRUCTION.json`. The private source package is not bundled here.
3. **L3 — raw observations to refitted models and results: not demonstrated.** `rebuild_tables.py` consumes previously fitted runs; source code presence is not a fresh refit.

## Rights status

This public release contains NBA.com-derived evaluation tables. **No redistribution licence is asserted.** `RIGHTS.md` records this as an open standing risk. The release decision was made by the operator with that risk disclosed. If the derived-data release is later judged impermissible, the appropriate remedy is to remove or replace the affected public data—not to claim retroactive permission.

Sloan's competition rules make authors responsible for third-party permissions. Conference acceptance of a derived-data reproduction package and third-party redistribution permission are separate questions.

## Local reconstruction evidence

The retained private source checkout matched historical source revision `88473250c289ff8019a9ae6a389107d6d12d98c3`; 11,959 manifest entries were hash-verified. Archived fitted runs and fact tables reconstructed both evaluation tables with unchanged evaluation hashes. This establishes L2 reconstruction only; it does not establish public-source availability, L3 refitting, or redistribution permission.
