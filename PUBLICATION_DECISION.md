# Publication decision — PMI

status: PUBLISHED_ON_OPERATOR_AUTHORIZATION
public_remote: https://github.com/ghadfield32/ssac27-ratings-are-not-forecasts
approved_by: Geoffrey Hadfield
approved_at: 2026-10-01
release_candidate_commit: a5110b1190d18d30c378b9ef30f21d132ecf636a
public_tag: ssac27-pmi-rc2-20261001
authorization: "explicit operator instruction, 2026-10-01: 'complete this with full authorization and then push to main'"

This file was the P6 gate. It recorded `NOT_APPROVED_FOR_PUBLICATION` while the
candidate was local, and is updated here as the record of what was published.

## What was published, and from what

- The **exact reviewed RC2 commit** `a5110b11` / tag `ssac27-pmi-rc2-20261001`
  was pushed with no cleanup commits, no rewriting, and no "while we're here"
  edits. Everything before this record update is byte-identical to the reviewed
  candidate.
- The **public tag `ssac27-pmi-rc2-20261001` still points at `a5110b11`** — the
  reviewed bytes. Updating the *record* does not move the reviewed tag.
- Anonymous read access and full reproduction were verified from the public URL
  (see `REPRODUCTION_RECEIPT.json`).

## Gate state at publication

| Gate | State |
|---|---|
| G1 — data redistribution rights | **OPEN — an unresolved standing risk, not a blocker we cleared** |
| G2 — `source_data` gitlink | resolved in RC2 |
| G3 — hermetic environment | resolved in RC2 |
| G4 — operator approval | **granted** 2026-10-01 |
| G5 — independent review of the hygiene layer | resolved in RC2 |

## G1 is the thing to read carefully

The tracked evaluation tables are NBA.com-derived, and `RIGHTS.md` records no
licence to redistribute them. **No permission was obtained.** The publish
decision was the operator's, taken with that risk stated and unresolved.

If the operator later judges the derived-data release impermissible, the remedy
is to remove those four files from the repository and the manifest — not to
retroactively claim a permission. The science and the L1 reproduction do not
depend on resolving it in either direction; the *public data distribution* does.

## Remaining operator-only actions

1. Decide G1 explicitly: keep, replace with a permitted derived release, or remove.
2. Add the repository URL to the Sloan form and submit (see `SUBMISSION_CHECKLIST.md`).
3. Retain the submission receipt, timestamp, and the exact submitted abstract hash.


## Historical: why this file read NOT_APPROVED_FOR_PUBLICATION

While the candidate was local, this file recorded `NOT_APPROVED_FOR_PUBLICATION`
with `public_remote: none`, and it was the last file that would change before a
public repository was created. That is the correct state for a local candidate,
and it is preserved here so the record is auditable.

What was already true before publication (and was not by itself a reason to
publish):

- The frozen reported experiment reproduced from the four tracked data files.
- Local archived-fits→tables reconstruction passed (`LOCAL_SOURCE_RECONSTRUCTION.json`, L2).
- The artifact passed non-author reviews (`REVIEW.md`, `INDEPENDENT_REVIEW.md`).
- Tests passed, provenance hashes verified, no absolute paths and no credentials tracked.

Those established that the candidate was *reviewable*. Publication was a separate
operator decision, taken explicitly on 2026-10-01 with G1 unresolved.

## The two reviewable release options (unchanged)

Sloan makes authors responsible for third-party permissions, so one of these
remains the substantive choice:

1. **Derived-evaluation release** — publish only the derived per-game tables with
   the reproduction limit stated. This is what is currently published.
2. **Permission-cleared source/refit release** — obtain actual third-party
   permission and publish the full chain including source and a hermetic refit.

If neither clears the applicable requirement, the submission stays blocked.
