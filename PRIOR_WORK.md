# Primary precedents and contribution boundary

This is a targeted primary-source comparison, not an exhaustive literature review. Different targets, information sets and metrics prevent direct cross-paper score comparisons.

| Primary work | Relevant contribution | Consequence for this paper |
|---|---|---|
| [Sill (SSAC 2010), Improved NBA Adjusted +/- Using Regularization and Out-of-Sample Testing](https://www.sloansportsconference.com/research-papers/improved-nba-adjusted-using-regularization-and-out-of-sample-testing) | Ridge RAPM and out-of-sample evaluation are established. The project's previous full-text comparison records realized lineup participation in its held-out scoring. | Do not claim invention of ridge, RAPM or out-of-sample evaluation. State our projected-participation game-level information boundary explicitly. |
| [Petridis and Pelechrinis (2026), L-RAPM](https://arxiv.org/html/2601.15000v1) | Informed-prior lineup ratings; weekly expanding-window predictions of future possessions/lineup matchups. Player priors are prior-season RAPM. | Weekly updating and past-only testing are not novel by themselves. Its evaluated target/information class differs from projected-participation pregame game forecasts. No superiority claim without a matched implementation. |
| [Gneiting and Raftery (2007), Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf) | Proper scoring provides a basis for evaluating probabilistic forecasts. | Coverage alone is insufficient; report width and a proper interval score. No invented predictive distribution is assigned to residual-quantile intervals. |

## Defensible contribution statement

We present an audited case study showing how forecast calibration changes the apparent relative value of rebuilding an in-house player-rating implementation versus updating it. The operational comparison projects participation and uses historical past-only replay. Accounting gates, timing, common populations, uncertainty, and reproduction limits are explicit. The study establishes neither a defect in public RAPM nor accounting's isolated effect.

## Claims to remove or avoid

- "First weekly/past-only RAPM", "new regularisation" or "first out-of-sample player impact evaluation".
- Generalizing the authors' legacy implementation defect to public implementations.
- Translating normalized-rate error to betting edge using realized future pace.
- Inferring useful decisions from model-error improvement alone.
- Calling observed-lineup diagnostic Track A a deployable pregame forecast.
- Calling reused evaluation seasons untouched validation after recalibration or new diagnostics.

## Remaining literature work

A full-paper review should add primary modern calibrated team-strength/game forecasts, player-rating priors, participation prediction, dependent forecast comparisons and practical decision evaluation. Their absence is an open competitive-baseline limitation. Compare target, issuance information, cutoff, tuning, cohort and uncertainty rather than only paper title or published RMSE. Preserve abstract-only access labels where full text is unavailable.
