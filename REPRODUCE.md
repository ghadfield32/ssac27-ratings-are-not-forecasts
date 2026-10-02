# How to reproduce

Three reproduction levels are defined. **Level 1 is mandatory and is what this
package promises.** Levels 2 and 3 are recorded separately so that their status
is never inferred from the presence of source code.

Do not claim a higher level than the one actually executed.

---

## Level 1 — reported-statistics replay (executed; mandatory)

Regenerates every number in `abstract.txt` from the four tracked data files.
Needs only `numpy` and `pandas`.

```bash
python reproduce.py
```

- Inputs: `data/pmi_games_track_a.csv`, `data/pmi_games_track_b.csv`,
  `data/frozen_parameters.json`, `data/expected.json`.
- Checks: pooled and per-season RMSE, holdout interval coverage, and the paired
  game-bootstrap promotion intervals against `data/expected.json`.
- Must end with: `OK: every value matches the committed results`.
- Exit status is `1` if anything fails to match.

Track B (projected participation) is the operational pregame track. Track A uses
observed participation and is a diagnostic.

### Supplemental diagnostics (Level 1, post hoc)

```bash
python supplement_analysis.py --package . --output supplement
```

Binds the four inputs to the reviewed SHA-256 values in `input_bindings.json`
before writing, and rechecks them after. Produces `supplement/supplement_results.json`
and `supplement/SUPPLEMENT_RESULTS.md`. All its analyses are labelled **post hoc**
over a spent holdout.

### Tests

```bash
python -m pytest test_supplement.py -q
```

The synthetic regression suite. It has passed all 14 tests in the author's
environment (10 test functions; the executed run including parametrised cases
reports 14).

---

## Level 2 — evaluation-table reconstruction from retained inputs (local only)

Executed **locally**, not from this package. `rebuild_tables.py` consumes
previously fitted runs and expects a complete source package:

```bash
python rebuild_tables.py
```

The default linked-source path is **currently unavailable in this package**
because `source_data/` is empty and `.gitmodules` has a placeholder remote. Do
not run a submodule command expecting a working public data repository.

What was actually done (see `LOCAL_SOURCE_RECONSTRUCTION.json`): a separate
existing local source checkout at revision
`88473250c289ff8019a9ae6a389107d6d12d98c3` was verified against all 11,959
manifest entries and used to reconstruct both 10,466-row / 20-column evaluation
tables to tolerance `1e-9`. Exactly one `SRC` assignment in the runner was
redirected in memory; its scientific functions and original files were unchanged.

This is **archived fitted runs → tables**, not raw-only refitting, not
permission clearance, and not an anonymous public-clone reconstruction.

---

## Level 3 — raw observations → refitted models → results (NOT executed)

Not demonstrated by either command above. A future hermetic refit must pin
inputs, code, settings, environment, and exact output equivalence. **This level
has never been run and must not be claimed.**

---

## Environment

`requirements.txt` (runtime), `requirements-verified.txt` (the direct-dependency
snapshot of the environment that reproduced the results), `requirements-dev.txt`
(tests), `requirements-rebuild.txt` (Level 2).

`requirements-verified.txt` pins `numpy==2.3.5` and `pandas==2.3.3`. It is a
**direct-dependency snapshot, not a complete transitive lock** — a hermetic
fresh-clone claim is not yet supported (gate G3).

---

## What "reproduce" does not mean here

- It does not reproduce raw NBA observations.
- It does not establish third-party redistribution rights.
- It does not turn the spent 2023-24/2024-25 holdout into fresh validation.
- Byte identity is not proof of historical information availability.
