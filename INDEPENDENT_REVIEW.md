# PMI — independent review of record

This is the source of record for the independent reviews of this package. Both
were performed by a **non-author, read-only** session with a fresh context.
That is artifact-author independence within the same harness family — **not** an
external conference or peer review, and **not** a second GitHub identity.

## RC1 — reviewed science artifact (2026-10-01)

Reviewer run ID: `pmi_submission_review` (read-only, assignment declared).
Exact resolved model/provider revision was not exposed.

| Phase | Verdict | Findings |
|---|---|---|
| Initial | REVISE | one MAJOR (PMI-R01); no BLOCKER |
| Focused remediation | **APPROVE** | zero unresolved reachable in-scope BLOCKER/MAJOR |

**PMI-R01 (MAJOR, closed).** Malformed or missing seasons and inconsistent game
identities/dates could pass validation. The actual inputs were valid, so the
finding did not invalidate the reproduced numbers. It was closed by strict
malformed-data refusal: five metadata-corruption probes and four bound-input
mutations all refused before output creation.

Independently reproduced by the reviewer: numerical results, input hashes,
interval score, calendar-contrast intervals, counts, abstract and figures. The
CLI was executed with output captured in memory; JSON and Markdown matched the
saved results exactly, with inputs unchanged. Four applicable read-only pytest
tests passed; ten fixture-writing tests were not rerun. Canonical title agrees
across abstract/manuscript/README. Reviewer word count: 402 including
title/body/table after stripping Markdown. Byte identity was correctly
distinguished from historical information availability.

Reviewed revisions (SHA-256):

| Artifact | SHA-256 |
|---|---|
| `supplement_analysis.py` | `5ee695524201cd6f4c0551afeabeb530d988bdfd7a73b55271ca6c523d1622db` |
| `abstract.md` | `d7429ed27b16c598e90b2ea2382e40f6719c22ef2aa875a19c843ee867f4b66e` |
| `input_bindings.json` | `56e0d89c46526ee2d84a50fe208d3f670ab6bed24d1a00e81d5dafe8ee128403` |
| `supplement/supplement_results.json` | `b3341e455526bfd5fbf9b5153e7272adc9fcacfaa813a6958bea564875520994` |

## RC2 — freeze review of the exact candidate commit (2026-10-01)

Scope: the whole candidate at a single frozen commit, covering both the
scientific layer and the newly created release-hygiene artifacts. Findings,
severities, evidence and closure are recorded in `REVIEW.md`.

## What neither review covers

Rights clearance (`RIGHTS.md` remains not publication-cleared), a real public
URL, conference-form verification, and the L2/L3 reproduction levels. Local
review is not conference or publication approval.
