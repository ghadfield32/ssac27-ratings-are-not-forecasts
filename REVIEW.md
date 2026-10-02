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

- Rights / data inventory (`RIGHTS.md` remains not publication-cleared).
- A real accessible support repository and public URL.
- Final conference-form verification.
- The release-hygiene artifacts added 2026-10-01 (`RELEASE_STATUS.yaml`,
  `PUBLICATION_DECISION.md`, `THIRD_PARTY_NOTICES.md`, `REPRODUCE.md`, this
  file, `DATA_INVENTORY.md`) — those are **not** covered by the review above.
- The clean-clone Level-1 reproduction (recorded in `REPRODUCTION_RECEIPT.json`).

The reviewer edited no files.
