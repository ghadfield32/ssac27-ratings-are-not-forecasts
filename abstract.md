## Ratings Are Not Forecasts: A Past-Only Test of NBA Player-Impact Models

**Introduction.** Adjusted plus-minus ratings drive player evaluation. Their classic out-of-sample test (Sill, SSAC 2010) scored held-out games using the lineups that actually played; a pregame forecast must also project who will play. We ask how reconciled possession accounting and past-only updating change the game forecasts of our in-house ratings, using only information available before tip-off.

**Methods.** Our earlier in-house ratings counted play-by-play rows as possessions; rows are only about half of real possessions. We rebuilt possession accounting from play-by-play for 2015-16 to 2024-25. Every possession must be attributed and credited points must equal box-score points; games without source play-by-play (8 to 61 per season) are declared and excluded, and any other failure fails the season. We forecast the home margin per 100 combined (both-team) possessions, with participation projected from past games. The candidates were home court alone; prior-season legacy ratings; prior-season reconciled ratings, which differ from legacy only in possession accounting and tuned regularisation; and reconciled ratings refit weekly from past games only. Contracts and parameters were frozen before a single read of 2,430 held-out games (2023-24 and 2024-25), a historical past-only replay.

**Results.** Weekly past-only ratings had the lowest error (Table 1). Their paired game-level 95% intervals excluded zero against every baseline (vs prior-season reconciled: −0.28 to −0.16). The legacy ratings were on the wrong scale: their development-fitted calibration slope was 0.47, so their forecasts were about twice too extreme. Post hoc, after rescaling every rating-based model using development seasons only, prior-season reconciled ratings still beat legacy ratings by 0.14 (−0.19 to −0.09) at identical information timing. Weekly updating added a further 0.22, a gain of similar size (the two were not tested against each other, and their order reversed in 2023-24). The weekly model's nominal 80% intervals covered 77% of games.

**Conclusion.** Our earlier ratings were about twice too extreme, a scale error consistent with counting rows as possessions (regularisation also differed), and it cost most of their forecasting value. Rescaling recovered most of that loss, but not all of it; updating from recent games added a gain of similar size. Teams that use impact ratings to anticipate games should reconcile possessions to the box score, check calibration, and test on past-only replays rather than in-season fit. We did not compare against betting markets.

**Table 1.** Holdout RMSE, home margin per 100 combined possessions (2,430 games).

| Forecast | As frozen | Rescaled on development seasons (post hoc) |
|---|---:|---:|
| Home court only | 7.944 | — |
| Prior-season legacy ratings | 7.761 | 7.471 |
| Prior-season reconciled ratings | 7.334 | 7.334 |
| Weekly past-only reconciled ratings | **7.113** | **7.113** |
