# Publication decision — PMI

status: NOT_APPROVED_FOR_PUBLICATION
public_remote: none
approved_by: null
approved_at: null
release_candidate_commit: null
public_tag: null

This file is the P6 gate. It is the last thing that changes before any public
repository is created. Until `approved_by` and `approved_at` are set by Geoffrey
Hadfield, **creating a public repository, adding a GitHub remote, or pushing
publication bytes is outside the authorization of any agent session.**

## Why it is not approved

Four gates are open. None of them is a code defect; all four are decisions or
evidence that only the operator can supply.

| Gate | State | Why it blocks publication |
|---|---|---|
| G1 — data redistribution rights | open | The tracked evaluation tables are NBA.com-derived (`DATA.md`: attribution, not permission). `RIGHTS.md` states the package is **not publication-cleared**. A MIT code licence cannot grant third-party data rights. |
| G2 — `source_data` gitlink | open | The submodule is an empty `160000` gitlink (`88473250…`) with the **placeholder** remote `github.com/YOUR-ACCOUNT/ssac27-pmi-source-data.git`. Pushing this state would publish a broken/placeholder reference as if it were a data repository. |
| G3 — hermetic environment | open | `requirements-verified.txt` is a direct-dependency snapshot, not a transitive lock. A fresh-clone reproduction cannot yet be called hermetic. |
| G4 — operator approval | open | This file. |

## What is already true (and is not a reason to publish)

- The frozen reported experiment reproduces from the four tracked data files (`reproduce.py`).
- Local archived-fits→tables reconstruction passed (`LOCAL_SOURCE_RECONSTRUCTION.json`, L2).
- The artifact passed a non-author review (`INDEPENDENT_REVIEW.md`: APPROVE, one MAJOR closed).
- Tests pass; provenance hashes verify; no absolute paths and no credentials are tracked.

These establish that the *candidate is reviewable*. They do not establish that the
*content is publishable*. Reviewability is a precondition for this decision, not a
substitute for it.

## The two reviewable release options

The author must choose one, because Sloan makes authors responsible for
third-party permissions:

1. **Derived-evaluation release.** Publish only the derived per-game evaluation
   tables with an explicit statement of the reproduction limit (L1, plus L2
   described as local-only). Requires the conference to accept that scope.
2. **Permission-cleared source/refit release.** Publish the full chain including
   source and a hermetic refit. Requires actual third-party permission and a
   resolved `source_data` reference.

If neither clears the applicable requirement, the submission stays blocked.

## How to approve

After inspecting the repository, give the explicit instruction:

> Approve PMI release candidate `<commit>` for public publication.

Then — and only then — set `approved_by`, `approved_at`, and
`release_candidate_commit` above, create the public repository from that exact
commit, and record `public_tag`. No cleanup commits between approval and
publication unless they are reviewed too.
