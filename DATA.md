# Data, provenance and reproduction boundary

Statistics underlying this study originate from **NBA.com**. The evaluation tables and predictions are derived research artifacts. This statement is attribution, not permission to redistribute underlying or derived content. MIT code licensing does not license third-party data.

## Existing inputs read in this update

| Input | Purpose | State |
|---|---|---|
| `data/pmi_games_track_a.csv` | Actual-participation diagnostic evaluation | Existing 10,466-row table, read-only |
| `data/pmi_games_track_b.csv` | Projected-participation operational evaluation | Existing 10,466-row table, read-only |
| `data/frozen_parameters.json` | Development-frozen offsets/residual quantiles | Existing file, read-only |
| `data/expected.json` | Original result checks and previous recalibration | Existing file, read-only |

Exact SHA256 values are in `supplement/supplement_results.json` and the private verification receipt. This update includes no copied source data, CSVs, player identities, raw events, fitted-run archives or credentials. It is an overlay on the existing local package, not a complete standalone data release.

## Units and columns

`ACTUAL` is 100 times home-minus-away credited points divided by combined home-and-away reconciled possession counts. It is not the usual per-100-one-team-possession net rating or raw point margin. `PLAYER_PART_<model> + h` is the frozen forecast in that unit.

`GAME_ID` is a string preserving leading zeros. `PHASE` identifies development or holdout, `EVAL_ORDER` preserves original row order, and `MATCHED` identifies the common scoring population. Missing predictions in unmatched rows remain missing; missing values in matched rows refuse analysis.

**`WEIGHT` is track-specific.** Track A contains observed combined stint possessions. Track B is 480 (two teams' 240 projected minutes). It represents the projected-minute exposure denominator used by the executed code, **not possessions in the game**. The existing package's generic description of this column must be corrected. The original pooled RMSE is game-weighted, not possession-weighted.

Rating coverage is the evaluated share with explicit ratings, not schedule coverage or proof of complete source data. The original implementation gives unrated players zero coefficient in its rating sum and reports their share. That executed convention is disclosed rather than silently changed in this update.

There are 8,017 matched development and 2,430 matched holdout games per track. Track B has 19 unmatched rows: 15 development and 4 holdout. These CSV-row exclusions are separate from source exclusions and no-valid-lineup gaps upstream; they must not be conflated into an all-scheduled-games coverage estimate.

Existing `EARLY_SEASON`, `ROOKIE_HEAVY` and `TEAM_CHANGE` flags are descriptive strata. In the original code, early season is the first 20% of admitted games; rookie-heavy is above the matched-phase median; team-change uses recorded earlier history. In particular the phase-wide rookie threshold is not an issuance-time routing rule. These flags do not prove externally timestamped historical availability.

## Upstream source exclusions

The executed possession release policy admits named source-absence **and source-order** exclusions, 8-61 per season. In 2024-25, all eight excluded games are source-order exclusions, not missing play-by-play. Other unratified failures fail the season. Equality of credited and box points validates scoring accounting; it does not prove physical-possession measurement is perfect.

## Three distinct reproduction claims

Saved-forecast reproduction is executed. The default linked-source reconstruction path remains unavailable because `source_data/` is empty and `.gitmodules` has a placeholder. Separate local archived-fit reconstruction has now passed as recorded below; anonymous public-source reconstruction remains unverified. Raw-data refitting is not demonstrated by `rebuild_tables.py`: that command consumes previously fitted runs. Neither the presence of fitting source code nor a previous archival restore is a fresh public clean-room refit.

## Release decisions still required

The author must resolve a permissible inventory and a real accessible supporting repository. The conference requests research data and makes authors responsible for third-party permissions: [official rules](https://www.sloansportsconference.com/research-paper-competition). No academic exemption, anonymization exemption, company/non-profit equivalence or permission to publish raw NBA content is inferred here. The author's supplied affiliation is World model Sports LLC.

Two reviewable options remain: a permitted derived-evaluation release with an explicit description of its reproduction limit, subject to conference acceptance of that scope; or a permission-cleared source/refit release with the full chain. If neither clears the applicable requirements, the submission must remain blocked. Do not publish the empty source submodule as proof of either option.

## Local reconstruction evidence added Oct. 1

The separate existing local source checkout matches the recorded source gitlink revision 88473250c289ff8019a9ae6a389107d6d12d98c3. All 11,959 source manifest entries were hash-verified. Archived fitted runs and fact tables reconstructed both 10,466-row/20-column evaluation tables to 1e-9, with unchanged evaluation input hashes. The original runner was configured in memory by redirecting exactly one SRC assignment; no source/data/code file was changed. This is level-2 local reconstruction, not raw-only model refitting, public-source access or third-party permission. The README's non-commercial academic-publication assertion in that source package is not a recorded rights approval. See LOCAL_SOURCE_RECONSTRUCTION.json.
