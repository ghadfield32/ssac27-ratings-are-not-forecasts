## Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting

**Introduction.** NBA teams use player-impact ratings to compare players, but a rating is not a forecast. Turning ratings into a pregame game forecast also requires correct statistical units, an estimate of who will play, a calibrated forecast scale and information available before tipoff. We ask how much each of these choices changes the apparent value of an in-house player-impact model.

**Methods.** Our legacy ratings incorrectly treated play-by-play rows as possessions, producing counts only 0.48-0.56 of box-score possession estimates. We rebuilt the accounting and rating pipeline for 2015-16 through 2024-25, requiring reconciled possession attribution and credited points matching box scores. Declared source-absence/order exclusions removed 8-61 games per season; other failures failed the season. We forecast home margin per 100 combined possessions using projected participation from earlier games, comparing home court alone, legacy prior-season ratings, reconciled prior-season ratings, and reconciled ratings updated weekly from earlier games. Accounting and regularisation changed together, so their effects cannot be isolated. Models and parameters were frozen before evaluating 2,430 games in 2023-24 and 2024-25, after development on 8,017 earlier games.

**Results.** Weekly ratings produced the lowest frozen RMSE in both evaluation seasons and pooled (Table 1). Weekly-minus-baseline paired game-bootstrap 95% intervals excluded zero: home court -0.95 to -0.71, legacy -0.76 to -0.53, reconciled -0.28 to -0.16. Their development calibration slope was 1.00, against 0.90 for prior-season reconciled and 0.47 for legacy ratings: the legacy forecasts were badly scaled. Post hoc, after examining evaluation results, we rescaled forecasts using development seasons only. Legacy RMSE improved from 7.761 to 7.471. Reconciled ratings still beat rescaled legacy by 0.14 (0.09-0.19); weekly updating beat rescaled prior-season reconciled by 0.22 (0.16-0.28). Calibration thus reversed which component appeared more important. Post hoc 7-, 14- and 28-day calendar-block sensitivity retained both gains. These saved-forecast contrasts exclude model-fitting uncertainty. The weekly model's nominal 80% intervals covered 77% of evaluation games.

**Conclusion.** A large apparent improvement in player-impact forecasting can partly reflect forecast scale rather than better player information. After calibration, rebuilding the rating system and updating it weekly both retained smaller gains, with updating the larger. Teams should evaluate ratings as complete pregame forecasting systems: reconcile units, calibrate scale, project participation and enforce past-only information. This diagnoses our own implementation; it does not establish superiority over public RAPM models or betting markets, and operational decision benefits were not tested.

**Table 1.** RMSE, home margin per 100 combined possessions; 2,430 evaluation games.

| Forecast | Frozen | Calibration slope | Development-rescaled, post hoc |
|---|---:|---:|---:|
| Home court only | 7.944 | - | - |
| Prior-season legacy | 7.761 | 0.47 | 7.471 |
| Prior-season reconciled | 7.334 | 0.90 | 7.334 |
| Weekly reconciled | 7.113 | 1.00 | 7.113 |
