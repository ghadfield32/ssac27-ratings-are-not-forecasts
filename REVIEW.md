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
- Word count: 402 including title/body/table after stripping Markdown — **as of this review's abstract revision**. The abstract was revised afterwards (see the focused review below), so the current counts are 425 ordinary / 403 aggressive.
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

- Rights / data inventory (`RIGHTS.md` is the in-package authority; it records no redistribution licence, so gate G1 remained open at review time).
- A real accessible support repository and public URL **at review time** (none existed then; the repository was subsequently published under operator authorization).
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
| Initial freeze review | **REVISE** — 2 MAJOR, 4 MINOR, 3 INFO (9 findings) |
| Focused remediation review | **APPROVE** — both MAJORs closed; 4 new MINOR/INFO delta findings, all then closed |

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
| PMI-RC2-03 | MINOR | Inventory counts wrong (68 vs 72 tracked; 22 vs 23 `pipeline/**`). | Recomputed from `git ls-files`: 74 tracked, 23 `pipeline/**`, 71 payload files. |
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

Both MAJORs and all MINORs are closed above.

## Focused remediation review (2026-10-01)

A separate read-only non-author session reviewed the remediation commit itself,
checking each finding against the repository rather than against prose.

**Verdict: APPROVE.** Both MAJORs were closed on the underlying inconsistency:

| Finding | Verdict | Closing evidence |
|---|---|---|
| PMI-RC2-01 | **CLOSED** | `RIGHTS.md` is tracked; all 10 citations resolve; it states `NOT PUBLICATION-CLEARED` and grants nothing. |
| PMI-RC2-02 | **CLOSED** | No imperative submodule instruction remains; running `rebuild_tables.py` exits 1 with the corrected external-source message. |
| PMI-RC2-03 | **CLOSED** | All four counts now match `git ls-files` (74 tracked, 23 `pipeline/**`, 71 payload, 0 gitlinks). |
| PMI-RC2-04 | **CLOSED** | `PUBLICATION_DECISION.md`, `RELEASE_STATUS.yaml` and `RELEASE_CANDIDATE.json` agree: G1/G4/G5 open, G2/G3 resolved. |
| PMI-RC2-05 | **CLOSED** | README boundary sentence corrected; stale placeholder sentence gone; RC2 artifacts listed. |
| PMI-RC2-06 | **CLOSED** | Bullets split; no `.md` phantom outside this remediation table. |
| PMI-RC2-07 | **CLOSED** | Receipt line qualified as a host venv, not a container image. |
| PMI-RC2-08 | **Reported** | Tag created at the freeze boundary, after this review. |

The reviewer also independently confirmed the science layer unchanged and still
reproducing from a throwaway clone: `reproduce.py` exit 0, supplement exit 0
regenerating `b3341e45…`, 14 tests passed, `SHA256SUMS` 71/71 with 0 mismatches,
`abstract.md` still `d7429ed2…`, and the evaluation tables still 10,466 rows.

### Delta findings found by the remediation review, and their closure

| ID | Severity | Finding | Closure |
|---|---|---|---|
| RC2R-01 | MINOR | An absolute host path had leaked into `REPRODUCTION_RECEIPT.json`, making two of its own hygiene claims false. | Path replaced with a relative description; both claims re-verified true. |
| RC2R-02 | MINOR | The `PMI-RC2-03` closure cell cited stale intermediate counts (72/69). | Updated to 74/71. |
| RC2R-03 | INFO | The verdict row said 5 MINOR while the table listed 4. | Corrected to 4 MINOR / 9 findings. |
| RC2R-04 | INFO | Two residual Markdown nits in this file. | Corrected. |

RC2R-01 is the same defect class as the MAJOR it followed: a document asserting
something untrue about itself. It was introduced by the remediation and caught by
reviewing the remediation — which is the argument for reviewing the delta rather
than accepting a closure on the strength of added sentences.

## What the RC2 review could not verify

- **L2** — the private source checkout at `88473250…` is not present, so the
  11,959-entry manifest verification and the 1e-9 table reconstruction could not
  be re-run. Taken on record, as the package itself states.
- **L3** — never executed; nothing claims otherwise.
- **Upstream NBA.com fidelity** — by design: L1 replays the derived tables only.
- **G1 rights** — a legal/operator judgment, outside scientific verification.
- **`uv sync --frozen`** — the lock was verified statically; a network install
  was not executed by the reviewer.

The candidate was **NOT_APPROVED_FOR_PUBLICATION** at review time, pending the
operator's own decision (gate G1). It was subsequently published under explicit
operator authorization; G1 remains an open standing risk, not a cleared gate.
See `PUBLICATION_DECISION.md` for the current publication record.

---

# Focused review of the revised abstract (2026-10-01)

Scope: the abstract revision only, plus a regression check that nothing else
moved. Reviewer: a fresh, non-author, read-only session with an independent
context, which recomputed every number with its own code rather than through
`reproduce.py`.

## Verdict: APPROVE — zero BLOCKER/MAJOR

The revision changed wording, not findings, and the reviewer confirmed it does
**not** introduce or strengthen any claim. It verified that the package still
argues against a solo-accounting reading (`not an isolated accounting treatment`,
`cannot isolate accounting from regularisation`) and that nothing compares
against public RAPM implementations.

## Independently recomputed (all matched)

Frozen RMSEs 7.944 / 7.761 / 7.334 / 7.113 and rescaled 7.471; the three
weekly-minus-baseline intervals −0.9504..−0.7114, −0.7570..−0.5329,
−0.2821..−0.1591; development slopes 0.471 / 0.897 / 0.997; rescaled contrasts
0.1374 (0.0883–0.1870), 0.2214 (0.1576–0.2824), 0.3587 (0.2747–0.4412);
coverage 0.76996; population 8,017 / 2,430.

**The sign convention was confirmed independently:** the stored intervals are
`RMSE(weekly) − RMSE(baseline)`, which matches the new `Weekly-minus-baseline`
wording. The reviewer also confirmed Table 1 reports Track B, not Track A.

## Limitation audit against the previous revision

No limitation was dropped. All of these survive: accounting not isolated,
post-hoc labelling, saved-forecast conditioning, no betting market, no decision
value, diagnoses-our-build, spent holdout. (The spent-holdout caveat is absent
from *both* revisions — pre-existing, carried in the supplement's limitations —
not a regression introduced here.)

## Reproduction in a throwaway clone at this commit

`reproduce.py` exit 0; `supplement_analysis.py` exit 0; **14 tests passed**;
regenerated `supplement_results.json` byte-identical to `b3341e45…`; `SHA256SUMS`
71/71 with 0 mismatches.

## Findings from this review

| ID | Severity | Finding | Closure |
|---|---|---|---|
| PMI-ABS-01 | MINOR | `0.48-0.56` and `8-61` are not reproducible from within the package; they trace only to the owner run-doc. | `CLAIM_LEDGER.md` and `MANUSCRIPT.md` now say so explicitly. |
| PMI-ABS-02 | MINOR | `REVIEW.md` / `INDEPENDENT_REVIEW.md` still stated "402 words", which no longer matched any count. | Framed as the count at that review; current 425 / 403 stated. |
| PMI-ABS-03 | MINOR | `SUBMISSION_CHECKLIST.md` claimed two word counts but stated none. | Both counts now stated. |
| PMI-ABS-04 | INFO | The `0.28` lower endpoint is round-half-up from a 0.275 source value. | Left as-is; the rounding under-claims rather than over-claims. |

The reviewer also noted that this commit's own message gave inconsistent word
counts for the previous revision. The substantive claim (that the revision gained
margin) holds: 425 ordinary / 403 aggressive, both under the 500 limit.

## What this review could not verify

The authoritative values behind `0.48-0.56` and `8-61` (the owner run-doc is
outside the package); L2/L3; upstream NBA.com fidelity; and G1 rights.


