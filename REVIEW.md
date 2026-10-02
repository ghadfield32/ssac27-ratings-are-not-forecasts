# Independent review record — PMI

## What was reviewed

The **local artifact**, not a public release. Review independence here is a
separate non-author read-only session with a fresh context. It is artifact-author
independence within the same harness family — **not** an external conference
peer review, and **not** a second GitHub identity.

- Reviewer run ID: `pmi_submission_review` (read-only, assignment declared).
- Exact resolved model/provider revision: not exposed.
- Source of record: `INDEPENDENT_REVIEW.md` (kept alongside the reviewed package).

## Verdict

| Phase | Verdict | Findings |
|---|---|---|
| Initial | REVISE | one MAJOR (PMI-R01); no BLOCKER |
| Focused remediation | **APPROVE** | zero unresolved reachable in-scope BLOCKER/MAJOR |

**PMI-R01 (MAJOR, closed):** malformed or missing seasons and inconsistent game
identities/dates could pass validation. The actual inputs were valid, so the
finding did not invalidate the reproduced numbers. Closed by strict malformed-data
refusal; five metadata-corruption probes and four bound-input mutations all
refused before output creation.

## What the reviewer independently reproduced

- All numerical results, input hashes, interval score, calendar-contrast
  intervals, counts, abstract, and figures.
- The CLI executed with output captured in memory; JSON and Markdown matched the
  saved results exactly, with inputs unchanged.
- Four applicable read-only pytest tests passed. Ten fixture-writing tests were
  not rerun by the reviewer.
- Canonical title agrees across abstract/manuscript/README.
- Word count: 402 (including title, body, and table, after stripping Markdown).
- Byte identity is correctly distinguished from historical information availability.

## Reviewed revisions (SHA-256)

| Artifact | SHA-256 |
|---|---|
| `supplement_analysis.py` | `5ee695524201cd6f4c0551afeabeb530d988bdfd7a73b55271ca6c523d1622db` |
| `abstract.md` | `d7429ed27b16c598e90b2ea2382e40f6719c22ef2aa875a19c843ee867f4b66e` |
| `input_bindings.json` | `56e0d89c46526ee2d84a50fe208d3f670ab6bed24d1a00e81d5dafe8ee128403` |
| `supplement/supplement_results.json` | `b3341e455526bfd5fbf9b5153e7272adc9fcacfaa813a6958bea564875520994` |

## What this review did NOT cover

This closes a local defect review, not any submission or publication gate.

- Rights / data inventory (`RIGHTS.md` is now the in-package authority; it remains not publication-cleared).
- A real accessible support repository and public URL.
- Final conference-form verification.
- The release-hygiene artifacts added 2026-10-01 (`RELEASE_STATUS.yaml`,
  `PUBLICATION_DECISION.md`, `THIRD_PARTY_NOTICES.md`, `REPRODUCE.md`, this
  file, `DATA_INVENTORY.json`, `RIGHTS.md`, `INDEPENDENT_REVIEW.md`, `SHA256SUMS`,
  `REPRODUCTION_RECEIPT.json`, `RELEASE_CANDIDATE.json`) — those are **not**
  covered by the RC1 review above.
- The clean-clone Level-1 reproduction (recorded in `REPRODUCTION_RECEIPT.json`).
- The RC2 changes (removed `source_data` gitlink, `pyproject.toml` + `uv.lock`,
  the rewritten `DATA_INVENTORY.json`). These are tracked as gate G5.
The reviewer edited no files.

---

# RC2 freeze review (2026-10-01)

Scope: the whole candidate at a **single frozen commit**, covering both the
scientific layer and the release-hygiene artifacts. Reviewer: a fresh,
non-author, read-only session with an independent context.

## Verdict

| Phase | Verdict |
|---|---|
| Initial freeze review | **REVISE** — 2 MAJOR, 5 MINOR, 3 INFO |
| Focused remediation | see the closure table below |

The reviewer reproduced the entire scientific layer independently — recomputing
every reported quantity from `data/pmi_games_track_b.csv` with its own code
rather than through `reproduce.py` — and found **no scientific defect**. All 17
checked quantities matched, including the four RMSEs, the calibration slope
0.471, the weekly-vs-reconciled interval, both rescaled contrasts, coverage
0.770, the calendar-block intervals, and the per-season ordering reversal. Its
adversarial attempts to falsify the headline claim, the "no accounting
isolation" caveat, and the reproduction-level claims all failed: the caveat is
present and strong, and no stronger wording exists anywhere.

The findings were in the release-hygiene layer, introduced or left by the RC2
surgery.

## Findings and closure

| ID | Severity | Finding | Closure |
|---|---|---|---|
| PMI-RC2-01 | MAJOR | Gate G1 rested on `RIGHTS.md`, which was **not tracked and never existed** in this repository (it was cited from a different location). A gate cannot rest on a missing authority. | Added `RIGHTS.md` as the in-package rights authority. `git grep RIGHTS.md` now resolves. |
| PMI-RC2-02 | MAJOR | `rebuild_tables.py` still instructed `git submodule update --init` and exited telling the reader to run it, contradicting the RC2 submodule removal. | Docstring and exit message now state the source is external and not a submodule. |
| PMI-RC2-03 | MINOR | Inventory counts wrong (68 vs 72 tracked; 22 vs 23 `pipeline/**`). | Recomputed from `git ls-files`: 72 tracked, 23 `pipeline/**`, 69 payload files. |
| PMI-RC2-04 | MINOR | `PUBLICATION_DECISION.md` said "four gates are open" while its table showed three. | Corrected to three (G1, G4, G5). |
| PMI-RC2-05 | MINOR | README claimed the environment was unverified in a fresh clone, and carried a stale placeholder sentence. | Both corrected; the RC2 artifacts were added to the file table. |
| PMI-RC2-06 | MINOR | `REVIEW.md` had two bullets merged on one line and referenced a nonexistent `DATA_INVENTORY.md`. | Split and corrected to `.json`. |
| PMI-RC2-07 | INFO | Receipt retained a pre-RC2 "no transitive lock" line. | Qualified as the pre-RC2 environment. |
| PMI-RC2-08 | INFO | The RC2 tag named in the identity files did not exist yet. | Created at the freeze boundary. |
| PMI-RC2-09 | INFO | `source_data/README.md` retained the literal placeholder URL. | Judged benign (past-tense and explanatory). Reworded for a clean scan. |

## What the RC2 review could not verify

- **L2** — the private source checkout at `88473250…` is not present, so the
  11,959-entry manifest verification and the 1e-9 table reconstruction could not
  be re-run. Taken on record, as the package itself states.
- **L3** — never executed; nothing claims otherwise.
- **Upstream NBA.com fidelity** — by design: L1 replays the derived tables only.
- **G1 rights** — a legal/operator judgment, outside scientific verification.
- **`uv sync --frozen`** — the lock was verified statically; a network install
  was not executed by the reviewer.

## Reviewer's conclusion

*"Do not approve for publication yet. Fix [the two MAJORs], reconcile the count
and gate-language drift, then the candidate's science and L1 release gates are in
a state I would approve."*

Both MAJORs and all MINORs are closed above. The candidate remains
**NOT_APPROVED_FOR_PUBLICATION** pending the operator's own decision (gate G1).

