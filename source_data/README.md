# Upstream source data — not bundled

This directory previously held a Git submodule pointer. It was **empty** and its
remote pointed at an unconfigured placeholder repository that has never existed,
which made a clone look like it needed a second repository. The pointer and
`.gitmodules` have been removed. This note replaces them.

## What was used privately

The study consumed NBA.com play-by-play and box-score data through the WMS
possession ledger and RAPM pipeline. The categories were:

| Category | Role | Bundled here? |
|---|---|---|
| Play-by-play event rows | Possession accounting, source of `ACTUAL` | **No** |
| Box scores | Possession/points validation targets | **No** |
| Rotations / lineup stints | Participation denominators | **No** |
| Player-level provider tables | Rating inputs | **No** |

These are third-party provider content. They are **not redistributed** in this
package and are not required for the reproduction level it supports.

## Why the raw source is not bundled

Data rights are unresolved. `RIGHTS.md` is explicitly not publication-cleared and
a MIT code licence cannot grant third-party data rights. Bundling raw provider
content would cross a boundary this package deliberately stays behind. See
`THIRD_PARTY_NOTICES.md` and `DATA.md`.

## What is bundled instead

- `data/pmi_games_track_a.csv`, `data/pmi_games_track_b.csv` — the derived
  per-game evaluation tables (10,466 rows each). These are the minimum input
  needed to recompute the reported statistics.
- `data/frozen_parameters.json` — development-only offsets and residual quantiles.
- `data/expected.json` — the committed expected values used as checks.

Their publication is **pending an operator decision** (gate G1). See
`DATA_INVENTORY.json`.

## The reproduction level this package supports

- **L1 — reported-statistics replay: supported.** `python reproduce.py`
  recomputes every abstract number from the bundled derived tables.
- **L2 — evaluation-table reconstruction from retained inputs: not supported
  here.** It was executed locally against a private source checkout
  (`LOCAL_SOURCE_RECONSTRUCTION.json`). It cannot be run from this package,
  because the upstream source it needs is not bundled.
- **L3 — raw observations to refitted models: not executed.**

Do not run a submodule command here. There is no submodule.
