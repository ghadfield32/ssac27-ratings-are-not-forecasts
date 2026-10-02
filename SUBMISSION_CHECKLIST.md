# PMI SSAC27 submission checklist

**Current decision: NOT READY TO SUBMIT.** The corrected text and local saved-forecast analyses are prepared, but the public repository/data-release gate remains open. No A grade, publication or submission is claimed.

## Prepared local deliverables

- [x] Author: Geoffrey Hadfield, World model Sports LLC, CEO/founder, supplied by the operator.
- [x] Introduction/Methods/Results/Conclusion and one table in the abstract.
- [x] Abstract below 500 words: 402 whitespace words / 438 conservative lexical words including title, headings, caption and table at this revision; verify again after edits.
- [x] The abstract uses **one table only**. The two supplemental figures belong to the manuscript/supporting material; attaching both to the abstract as well would exceed its combined figure/table allowance.
- [x] Existing quick reproduction executed; every committed value matched.
- [x] New supplement executed on both existing tables, preserving input hashes.
- [x] Tests cover invalid/missing inputs, timing, development-only scale, interval score and paired calendar resampling; 14 passed in 0.67s in the current author-run suite, including season/date/identity corruption and immutable input binding.
- [x] Source-absence/source-order wording corrected; no claim every exclusion is a missing feed.
- [x] Track B WEIGHT correctly documented as projected minutes, not possessions.
- [x] Calibration, weekly-update prior work, actual-participation oracle, unisolated accounting/regularisation, post hoc exposure and interval undercoverage disclosed.
- [x] Substantive manuscript, claim ledger, targeted primary comparison and future-study design prepared.
- [x] Separate non-author initial review identified one MAJOR metadata-validation defect; focused remediation approved the local artifact with zero unresolved in-scope BLOCKER/MAJOR findings. Exact reviewed supplement and abstract hashes are recorded in the parent packet's INDEPENDENT_REVIEW.md and verification receipt. This is not conference/publication approval.

## Required external/operator gates

- [ ] Decide the exact permissible data release and document third-party permission/disposition. Company affiliation and academic intent do not automatically establish redistribution rights.
- [ ] Confirm the released supporting data meet conference requirements, including the saved-forecast versus raw-refit distinction.
- [ ] Supply/create a real accessible public repository URL. Current package has no remote.
- [x] Removed the empty `source_data/` gitlink and its unconfigured placeholder remote, and replaced them with `source_data/README.md`. The candidate has zero gitlinks.
- [x] Added a transitive dependency lock (`pyproject.toml` + `uv.lock`) and verified it rebuilds the exact environment and runs the full suite.
- [ ] Publish only the reviewed permitted payload; verify access anonymously at the immutable release revision/tag.
- [ ] Check final form fields and copy the exact corrected abstract; choose basketball track. Confirm all final authors and required contact fields.
- [ ] Submit before **Oct. 1, 2026, 11:59 p.m. Eastern** and retain the actual receipt, timestamp, submitted text and repository revision.

Dates and rule source: [official competition page](https://www.sloansportsconference.com/research-paper-competition), checked Oct. 1. If invited, the full manuscript is due Dec. 4, 2026. The local manuscript is a draft; it has not been formatted or accepted against an invitation's full-paper instructions.

## Improvement work not completed by editorial fixes

- [ ] Comparable accounting/regularisation factorial and competitive calibrated controls.
- [ ] Permission-cleared hermetic raw-data refit and fresh environment verification.
- [ ] Genuine available-at pregame receipts and untouched future validation.
- [ ] Model-refitting/recurrent-team uncertainty and prospectively declared multiplicity controls.
- [ ] Demonstrated practical workflow benefit under a measured budget.

These are scientific scope decisions, not boxes that can be checked by writing a plan. The current grade is not automatically raised. FUTURE_STUDY_CONTRACT.md defines the next discriminating work.
