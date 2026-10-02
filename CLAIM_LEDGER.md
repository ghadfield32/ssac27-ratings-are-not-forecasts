# PMI claim ledger

Original code/evaluation: `e3140577b`; original evaluation contract: `420003edd`. Source inspection revision: `0e0906c0a8d7e61034abe85caf76aece07c203ed`. The private verification receipt binds exact current input and artifact bytes. Public release remains a separate gate.

| Claim | Evidence | Qualification |
|---|---|---|
| Legacy counts 0.48-0.56 of box possession estimates | Owner RUNDOC section 3a/3e | Estimates/proxies, not independent physical-possession truth; **not reproducible from this package** — the source run-doc is outside it |
| 8-61 excluded games per season | Owner RUNDOC source-absence-v2 table/reason counts | Includes source order; 2024-25 eight are source-order, not absent feeds; **not reproducible from this package** — the source run-doc is outside it |
| Scored points/attribution checks | Owner RUNDOC season-release validation | Within admitted source/policy; not all-scheduled coverage or perfect measurement |
| Weekly fitting strictly earlier than issuance | Owner RUNDOC section 3f; frozen fitting/evaluation source | Historical event-date replay; external available-at receipts not proved |
| 8,017 development/2,430 evaluation matched games | `data/*.csv`, frozen report; both reproduced | Selected admitted/matched population |
| Table 1 RMSE 7.944/7.761/7.334/7.113 | `reproduce.py` matches `data/expected.json`; original `d2_evaluation.md` | Track B, combined-possession normalized rate |
| Weekly beats three declared baselines in original paired game bootstrap, Track B intervals [-0.950,-0.711] home only, [-0.757,-0.533] legacy, [-0.282,-0.159] reconciled | Original D2 evaluation/bootstrap; quick reproduction | Conditional saved models; original promotion criterion is not production activation |
| Development calibration slopes 0.471 legacy, 0.897 prior-season reconciled, 0.997 weekly | Previous recalibration output and reproduced CSV regression | Post hoc study design; fit uses development labels only |
| Rescaled legacy RMSE 7.471; prior-minus-legacy -0.137, weekly-minus-prior -0.221, weekly-minus-legacy -0.359 | Previous recalibration output; quick reproduction | Unisolated accounting plus regularisation contrast; every rating model rescaled |
| Nominal 80% weekly interval coverage 77% | Frozen residual quantiles + evaluation outcomes | Undercoverage is retained, not hidden or recalibrated on evaluation |
| Calendar-cluster robustness, all 7/14/28 day lengths | New `supplement_results.json`, both tracks | Post hoc nonoverlapping season-stratified clusters; recurrent teams/fitting uncertainty unresolved |
| Relative contrast size reverses after calibration | New joint paired-draw gain-size contrast in supplement | Track B as frozen +0.204577; rescaled -0.083956, accounting-plus-regularisation gain minus update gain. Exploratory unadjusted intervals, not causal allocation |
| Proper 80% interval score 25.3493 weekly vs 26.1500 prior | New supplement, frozen intervals | Lower is better; untested score difference is descriptive, not a significance claim |
| Track B WEIGHT=480 projected minutes | Frozen `build_track_b` source and evaluation CSV | Not game possessions; pooled error is unweighted by WEIGHT |
| Track B 15 development/4 holdout unmatched rows | New supplement population counts | Distinct from upstream excluded or no-valid-lineup games |
| Author name/affiliation | Operator response 2026-10-01 | Geoffrey Hadfield, World model Sports LLC, CEO/founder |
| Public repository / derived-data release | PUBLICATION_DECISION.md records the public URL and the authorization | Repository is public; the derived-data redistribution question is explicitly unresolved and no permission was obtained; no source-data release exists |
| Conference submission | No evidence | No Sloan form submission and no receipt exists; do not claim submitted |

## Scientific findings left open

Pure accounting effect, equal-budget strong modern baselines, independently timestamped pregame data, fresh out-of-time confirmation, refitting uncertainty, practical decision improvement, full raw-data reproduction and external source-release compliance are not established. None is promoted from this manuscript's wording or a scorecard change.
