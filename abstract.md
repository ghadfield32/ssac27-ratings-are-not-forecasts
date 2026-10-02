## Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting

**Introduction.** Adjusted plus-minus ratings inform player evaluation, but a pregame forecast must also project who will play. We test how possession reconciliation, calibration and past-only updating change game forecasts from our in-house ratings. The contribution is an audited forecast comparison, not a new claim to regularisation or weekly updating.

**Methods.** Our earlier ratings counted play-by-play rows as possessions; counts were 0.48-0.56 of box-score possession estimates. We rebuilt accounting for 2015-16 through 2024-25. For accepted games, validation required possession attribution and credited points matching box-score points. Declared source-absence or source-order exclusions removed 8-61 games per season; failures outside that policy failed the season. We forecast home margin per 100 combined, both-team possessions, with participation projected from earlier games. Candidates were home court alone, prior-season legacy ratings, prior-season reconciled ratings, and reconciled ratings refit weekly from earlier games. Reconciliation and tuned regularisation changed together, so this is not an isolated accounting treatment. Contracts and parameters were frozen before reading the evaluation seasons, using historical past-only replay: 8,017 development games over seven seasons, then 2,430 evaluation games in 2023-24 and 2024-25.

**Results.** Weekly ratings had the lowest frozen error in each evaluation season and pooled (Table 1). Paired game-bootstrap 95% intervals excluded zero against all three declared baselines: home court alone -0.95 to -0.71, prior-season legacy -0.76 to -0.53, prior-season reconciled -0.28 to -0.16. Legacy forecasts were too extreme, with a development-fitted calibration slope of 0.47, against 0.90 for prior-season reconciled and 1.00 for weekly ratings. Post hoc, after examining evaluation results, we rescaled rating forecasts using development seasons only. At matched information timing, reconciled ratings beat rescaled legacy ratings by 0.14 (95% interval 0.09-0.19); weekly updating added 0.22 (0.16-0.28) over rescaled prior-season reconciled and 0.36 (0.28-0.44) over rescaled legacy. New post hoc calendar-block sensitivity retained both gains at 7, 14 and 28 days. Before rescaling, the accounting-plus-regularisation contrast exceeded the updating contrast; afterward their order reversed. These comparisons condition on saved forecasts and exclude model-fitting uncertainty. The weekly model's nominal 80% intervals covered 77% of evaluation games.

**Conclusion.** Calibration changes the apparent relative value of rebuilding ratings and updating them. After rescaling, reconciled ratings and weekly updating retained smaller gains, and this design cannot isolate accounting's effect from regularisation. Teams forecasting with impact ratings should audit accounting, calibrate forecasts, project participation and evaluate with past-only replay. This diagnoses our earlier build, not public RAPM implementations. Betting markets and operational decision benefits were not evaluated.

**Table 1.** RMSE, home margin per 100 combined possessions; 2,430 evaluation games.

| Forecast | Frozen | Calibration slope, development | Development-rescaled, post hoc |
|---|---:|---:|---:|
| Home court only | 7.944 | - | - |
| Prior-season legacy | 7.761 | 0.47 | 7.471 |
| Prior-season reconciled | 7.334 | 0.90 | 7.334 |
| Weekly reconciled | 7.113 | 1.00 | 7.113 |
