## Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting

**Introduction.** Adjusted plus-minus ratings inform player evaluation, but pregame forecasts must also project who will play. We test how possession reconciliation, calibration and past-only updating change game forecasts from our in-house ratings. This is an audited forecast comparison, not a claim to new regularisation or updating methods.

**Methods.** Earlier ratings counted play-by-play rows as possessions; row counts were 0.48-0.56 of box-score possession estimates. We rebuilt accounting for 2015-16 through 2024-25. Accepted games required possession attribution and credited points matching box-score points. Declared source-absence/order exclusions removed 8-61 games per season; other failures failed the season. We forecast home margin per 100 combined possessions, projecting participation from earlier games. Candidates were home court, prior-season legacy, prior-season reconciled, and weekly past-only reconciled ratings. Reconciliation and tuned regularisation changed together, so this is not an isolated accounting treatment. Contracts and parameters were frozen before reading evaluation seasons: 8,017 development games over seven seasons, then 2,430 evaluation games in 2023-24 and 2024-25.

**Results.** Weekly ratings had the lowest frozen RMSE in both evaluation seasons and pooled (Table 1). Weekly-minus-baseline paired game-bootstrap 95% intervals excluded zero: home court -0.95 to -0.71, legacy -0.76 to -0.53, reconciled -0.28 to -0.16. Development calibration slopes were 0.47 for legacy, 0.90 for prior-season reconciled and 1.00 for weekly ratings. Post hoc, after examining evaluation results, we rescaled rating forecasts using development seasons only. At matched information timing, reconciled beat rescaled legacy by 0.14 (95% interval 0.09-0.19); weekly beat rescaled prior-season reconciled by 0.22 (0.16-0.28) and rescaled legacy by 0.36 (0.28-0.44). Post hoc 7-, 14- and 28-day calendar-block sensitivities retained both component gains. Calibration reversed which component appeared larger. These saved-forecast contrasts exclude model-fitting uncertainty. The weekly model's nominal 80% intervals covered 77% of evaluation games.

**Conclusion.** Calibration changes the apparent importance of reconciliation/regularisation versus weekly updating. After rescaling, both retained smaller gains, but this design cannot isolate accounting from regularisation. Teams forecasting with impact ratings should audit accounting, calibrate forecasts, project participation and evaluate with past-only replay. This diagnoses our earlier implementation, not public RAPM models. Betting markets and operational decision benefits were not evaluated.

**Table 1.** RMSE, home margin per 100 combined possessions; 2,430 evaluation games.

| Forecast | Frozen | Calibration slope, development | Development-rescaled, post hoc |
|---|---:|---:|---:|
| Home court only | 7.944 | - | - |
| Prior-season legacy | 7.761 | 0.47 | 7.471 |
| Prior-season reconciled | 7.334 | 0.90 | 7.334 |
| Weekly reconciled | 7.113 | 1.00 | 7.113 |
