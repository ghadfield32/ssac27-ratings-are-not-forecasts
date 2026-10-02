# Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting

Geoffrey Hadfield, World model Sports LLC (CEO/founder)

**Status:** substantive manuscript draft accompanying an abstract candidate. Not submitted, publication-cleared or formatted against a future full-manuscript template. The original evaluation and newly executed post hoc analyses are separated throughout. This paper is a case study, not a claim of universal model superiority.

## Abstract

Player ratings require an additional participation model to become pregame game forecasts. We rebuilt possession accounting in an in-house NBA rating implementation, then compared home court alone, legacy prior-season ratings, reconciled prior-season ratings and weekly reconciled ratings using projected participation. Development contained 8,017 matched games; the frozen historical evaluation contained 2,430 games from 2023-24 and 2024-25. Operational RMSE was 7.944, 7.761, 7.334 and 7.113 respectively, in home margin per 100 combined possessions. Post hoc development-only calibration reduced legacy RMSE to 7.471. Reconciled ratings and updating retained smaller gains. Additional saved-forecast calendar-cluster diagnostics show that calibration reverses the apparent ordering of these two contrasts. The weekly model's nominal 80% intervals covered 77% of evaluation outcomes. These findings motivate explicit accounting, timing, calibration and participation contracts when evaluating rating-based forecasts. Accounting and regularisation changed jointly, and neither fresh prospective confirmation nor operational decision benefit is established.

## 1. Research question and contribution

Adjusted plus-minus estimates can be useful player summaries without constituting pregame forecasts. A forecast also needs an information cutoff, participation expectations, a target unit and calibration. Treating a rating as a forecast can confuse the quality of the player estimator with assumptions about who plays and the scale on which the prediction is expressed.

We ask a bounded question: how do rebuilding an in-house rating implementation, recalibrating its forecasts and updating ratings using earlier games change the errors of pregame game forecasts? Our contribution is an auditable comparison showing that calibration changes the apparent relative value of rebuilding ratings and updating them. The forecast information class and reproduction limits are explicit.

This does not introduce ridge regularisation, RAPM or out-of-sample testing. Sill's SSAC 2010 paper establishes that precedent. Weekly expanding-window evaluation also appears in L-RAPM, which predicts lineup/possession outcomes with informed priors. Our operational outcome is instead a game-level normalized home margin with projected participation. That distinction is a contribution boundary, not evidence that our system is stronger than those models. [Sill (2010)](https://www.sloansportsconference.com/research-papers/improved-nba-adjusted-using-regularization-and-out-of-sample-testing); [Petridis and Pelechrinis (2026)](https://arxiv.org/html/2601.15000v1).

## 2. Data and accounting

The accounting rebuild covers 2015-16 through 2024-25 using NBA.com-derived observations. The first season supplies earlier ratings for forecasts beginning in 2016-17. The legacy comparator is the authors' earlier in-house implementation. Its play-by-play-row denominator amounted to 0.48-0.56 of box-score possession estimates, exposing a unit/scale discrepancy. Box-score possession estimates are comparison proxies, not an independent observation of every physical possession.

The rebuilt pipeline attributes possessions and verifies that credited points match box-score points for accepted games. Named source-absence and source-order exclusions are declared. There are 8-61 excluded games per season; other failures outside the declared policy fail a season. In 2024-25 all eight exclusions are source-order failures. Describing them as absent play-by-play feeds would be incorrect. Scoring reconciliation does not establish perfect physical-possession identification; the declared same-team-repeat tolerance remains relevant.

The exported evaluation tables contain 10,466 rows per track. Across models, 8,017 development and 2,430 evaluation games are matched. Track B's 19 unmatched exported rows consist of 15 development and four evaluation games. These rows are separate from upstream source exclusions and no-valid-lineup gaps; the exported rows are not an all-scheduled-games coverage denominator. A future operational evaluation must retain every scheduled opportunity and score the fallback on unavailable cases.

Statistics underlying the work originate from NBA.com. This update reads existing artifacts without redistributing source data. The public inventory, third-party permissions and accessible repository remain unresolved. See DATA.md for units, provenance and reproduction levels.

## 3. Target and forecast information

The outcome for game g is

`y_g = 100 * (home credited points - away credited points) / (home possessions + away possessions)`.

This is home net points per 100 **combined** possessions. It differs from ordinary point margin and from a conventional per-100-one-team-possession rating. We do not multiply forecasts by the game's realized future pace to claim a pregame point-spread forecast. A pace-converted forecast would require a separate pregame pace estimate and its own evaluation.

The operational Track B projects team participation from strictly earlier regular-season games. The executed code uses recent appearances to determine eligibility, averages minutes over a prior-game window and normalizes each team's projected minutes to 240. Rated player contributions are weighted by projected minutes divided by 48, summed for each team and differenced. Unrated players contribute zero coefficient under the original convention; the explicitly rated share is reported. This is not a newly inferred absence or a missing-value repair. The precise window constants remain in the frozen code.

Track A uses observed lineup participation. It helps diagnose the model under an information class that knows who actually played, but cannot be deployed as an ordinary pregame forecast. Its advantage is not a causal estimate of the value of better participation forecasts.

Track B's exported WEIGHT equals 480 projected team minutes, not game possession counts. Track A's WEIGHT is observed combined stint possession exposure. Pooled forecast errors are averaged equally across matched games. Rating coverage, interval coverage and scheduled-game coverage are distinct quantities.

Historical features and rating selection are event-date past-only. However, the current evidence does not establish independent external available-at timestamps for every source revision or an archive of live pregame forecasts. We describe historical replay accurately rather than treating event date as proof of contemporaneous data availability.

## 4. Models and original evaluation design

Four forecasts were declared: home court only; prior-season legacy ratings; prior-season reconciled ratings; and reconciled ratings issued weekly from earlier data. Each combines its player component with a development-estimated home offset. The weekly candidate uses training data strictly earlier than its issuance and a prior-season regularisation choice.

The prior-season legacy and reconciled comparisons use matched information timing and share declared pooling, decay and stint-filter settings. They differ in both accounting and regularisation: the legacy build uses a fixed penalty whereas the rebuilt estimator tunes it. Their contrast must therefore be called accounting **plus regularisation**, not accounting alone. Comparing the same numerical penalty under different target and observation normalizations would not automatically repair that confounding.

The evaluation contract was frozen at commit `420003edd`. Development evidence was committed at `717b0b604` before the evaluation was read on 2026-09-26. Development uses 2016-17 through 2022-23; evaluation uses 2023-24 and 2024-25. The reference code is `e3140577b`. The originally declared promotion criterion required the weekly model's paired game-bootstrap 95% RMSE difference interval to lie below zero against every baseline in both tracks. That scientific criterion does not authorize a production deployment or metric-generation promotion.

Original offsets and 10th/90th residual quantiles were estimated on development games and frozen. Original uncertainty resamples paired matched games 2,000 times with seed 20260926. It conditions on the fitted models and does not fully account for recurrent teams, serial dependence or rating-refitting uncertainty.

## 5. Original results

Table 1 reports the operational Track B. The weekly candidate has the lowest frozen RMSE of the four declared models, both pooled and in each evaluation season. Against the three declared baselines the original paired game-bootstrap intervals are approximately [-0.950, -0.711] against home court alone, [-0.757, -0.533] against prior-season legacy ratings and [-0.282, -0.159] against prior-season reconciled ratings. Evaluation MAE is 5.578 for weekly and 5.753 for prior-season reconciled ratings. Results favor the weekly candidate under the original bounded comparison, not against every plausible sports forecasting model.

**Table 1. Operational evaluation, 2,430 matched games.** Units: home net points per 100 combined possessions. Rescaling was added after evaluation exposure.

| Forecast | Original RMSE | Development slope | Development-rescaled RMSE, post hoc |
|---|---:|---:|---:|
| Home court only | 7.944 | - | Not rescaled |
| Prior-season legacy | 7.761 | 0.471 | 7.471 |
| Prior-season reconciled | 7.334 | 0.897 | 7.334 |
| Weekly reconciled | 7.113 | 0.997 | 7.113 |

In diagnostic Track A, weekly RMSE is 7.076 versus 7.301 for prior-season reconciled ratings. Realized participation is withheld from the operational result. Track differences should not be interpreted as a clean treatment effect.

The weekly residual-quantile interval covers 77.0% of evaluation games rather than the nominal 80%. Retaining that undercoverage is essential: point accuracy does not establish calibrated uncertainty. No evaluation-fitted interval repair is presented as prospective validation. The distribution of interval widths, coverage and tail misses is shown in Figure 2.

## 6. Post hoc calibration and robustness

After reading the evaluation, we fitted linear forecast scale and intercept on development games only and applied them to evaluation games. This uses no evaluation labels in coefficient estimation, but the decision to add this analysis was post hoc. The legacy development slope is 0.471, against 0.897 for prior-season reconciled and 0.997 for weekly reconciled ratings: the legacy forecast is the badly scaled one. Its RMSE falls from 7.761 to 7.471 after rescaling. Reconciled prior-season ratings still outperform rescaled legacy forecasts by approximately 0.137, weekly updating outperforms the rescaled prior-season reconciled forecast by approximately 0.221, and weekly updating outperforms the rescaled legacy forecast by approximately 0.359. The earlier paired game-bootstrap recalibration intervals exclude zero for all three contrasts.

The new supplement adds joint calendar-cluster sensitivity, preserving all 7-, 14- and 28-day results. Nonoverlapping blocks are anchored to Monday within each season, paired model squared errors travel together, and blocks are resampled independently within season. Original season game weights are fixed when combining each resampled season mean. There are 2,000 resamples with seed 20261001. These are exploratory fixed-prediction sensitivities, not a replacement for the original frozen inference or a complete solution to dependence.

For the operational weekly-minus-prior contrast, calendar RMSE intervals are [-0.291, -0.151], [-0.303, -0.143] and [-0.303, -0.155] at 7, 14 and 28 days. After development rescaling, prior-minus-legacy intervals are [-0.190, -0.082], [-0.183, -0.096] and [-0.189, -0.093]. The improvement direction survives these declared sensitivity lengths. Figure 1 shows the development-only calibration and the resulting reordering of the two gains.

We also directly compare the two apparent gains using the same paired bootstrap draws. Define

`D = (RMSE_legacy - RMSE_prior) - (RMSE_prior - RMSE_weekly)`.

Before rescaling, D is +0.2046: rebuilding with changed regularisation appears more valuable. After development-only rescaling, D is -0.0840: updating appears more valuable. All three exploratory calendar intervals exclude zero in the corresponding directions. At 28 days the rescaled interval is [-0.1635, -0.0197]. This provides a more precise conditional statement than inferring relative gains from overlapping separate intervals. It is not a causal decomposition, and the ordering reverses within one of the two individual evaluation seasons. The point of the comparison is that calibration changes the apparent story told by the model ladder.

Additional interval diagnostics use the proper central-80% interval score:

`IS = (upper-lower) + 10*max(lower-y, 0) + 10*max(y-upper, 0)`.

Weekly mean interval score is 25.3493 versus 26.1500 for prior-season reconciled ratings; interval widths are 16.6529 versus 16.9933. Lower score is better. These differences are descriptive; a score-difference significance test was not performed. Width, coverage and both tail-miss rates are retained in the supplement. This avoids treating wider intervals as automatically better forecasts. [Proper scoring framework](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).

The supplement also retains original early-season, rookie-heavy and team-change strata and development-defined calibration bins. Subgroup analyses are descriptive, with overlapping populations and no multiplicity-controlled discovery claim. The original rookie-heavy threshold uses the matched-phase median; it is not available as a frozen pregame routing feature. No subgroup selection is used to improve the headline result.

## 7. Potential sports application

An analytics group converting player ratings into game expectations needs to distinguish three operational tasks: estimate impact, project participation, and calibrate the resulting forecast. An accounting error or poorly scaled comparator can inflate the apparent benefit of a new estimator. The case study supports an audit checklist: reconcile credited scoring and declared possession units, state the participation information set, calibrate on earlier observations, evaluate on a common temporal population, and report unavailable forecasts and uncertainty quality.

A concrete next application is allocating analyst review to games whose participation or rating uncertainty makes automatic forecasts unreliable. That workflow has not been evaluated. It would require a preregistered review budget, issuance-time routing variables, blinded or independently timestamped analyst revisions, a simple control policy and measured forecast/error reduction net of review cost. Observed errors or realized lineup knowledge cannot choose the cases retrospectively. Neither this candidate's RMSE improvement nor the presence of a production UI proves analyst time savings or decision utility.

## 8. Limitations and next discriminating study

The legacy model is in-house, so fixing its defects may not generalize to well-implemented public alternatives. Accounting and regularisation remain entangled. Baselines omit strong calibrated team-strength models, modern player-rating alternatives and betting markets. Market comparison, if added, must use the same pregame information cutoff; closing prices cannot support an earlier issuance claim.

The matched evaluation population excludes unavailable cases. Historical source availability and version custody are less complete than event-date ordering. Two evaluation seasons cannot establish stable generalization across future regimes. Both original and new uncertainty condition on saved fitted predictions; resampling model fitting, temporally dependent team effects and pipeline revisions remains open. The evaluation period is spent for further selection or tuning.

A controlled follow-up should use a common source/event population, accounting-by-update-by-calibration contrasts, comparable objective/penalty conventions and equal chronological tuning budgets. All models should use the same projected participation and timing. A fresh scheduled-game validation should capture externally verifiable issuance receipts, preserve fallback cases, and wait for outcome maturity. Its primary loss, smallest useful effect, sample precision and practical-use criterion must be frozen before outcomes are read. The detailed unexecuted contract is FUTURE_STUDY_CONTRACT.md.

## 9. Reproducibility and release state

The existing quick reproduction regenerated every reported abstract value locally. The new supplement records input hashes, refuses malformed or missing matched values, retains all declared analyses and verifies that inputs did not change. Its unit tests cover refusal, development-only scale fitting, hand-calculated interval scoring and paired season-stratified resampling.

This is saved-forecast reproduction. It is distinct from regenerating tables from archived fitted runs and from refitting ratings from raw observations. No upstream source is bundled: the placeholder source submodule was removed in RC2 and replaced by `source_data/README.md`. The pipeline source code does not make that release complete. A permission-cleared, accessible data inventory and public repository are still needed. No conference submission receipt exists in the inspected record.

## 10. Conclusion

In a frozen historical comparison, weekly reconciled ratings forecast game outcomes better than the three declared baselines. Development-only rescaling substantially reduces the legacy model's disadvantage and changes the apparent ordering of rebuilding and updating gains. The useful lesson is a disciplined comparison of accounting, information timing, participation and calibration. Stronger competitive baselines, isolated accounting evidence, fresh validation, operational utility and a complete permissible reproduction package remain necessary before making broader claims.

## References

- Sill, J. (2010). Improved NBA Adjusted +/- Using Regularization and Out-of-Sample Testing. MIT Sloan Sports Analytics Conference.
- Petridis, C., and Pelechrinis, K. (2026). Lineup Regularized Adjusted Plus-Minus (L-RAPM): Basketball Lineup Ratings with Informed Priors. arXiv:2601.15000v1.
- Gneiting, T., and Raftery, A. E. (2007). Strictly Proper Scoring Rules, Prediction, and Estimation. Journal of the American Statistical Association, 102(477), 359-378.

Internal reproducibility references: original D2 evaluation and owner RUNDOC at the declared source snapshot; previous recalibration output; the existing saved-forecast package; CLAIM_LEDGER.md; and the new supplemental JSON. Their presence is not a claim that a public release currently exists.
