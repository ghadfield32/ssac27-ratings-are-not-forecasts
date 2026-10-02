# PMI saved-forecast supplement

All analyses below are post hoc, conditional on the saved fitted forecasts.

## Operational Track B

| Model | RMSE | MAE | MSE | 80% coverage | Width | Interval score |
|---|---:|---:|---:|---:|---:|---:|
| B0_home_only | 7.944096 | 6.329085 | 63.108655 | 0.7621 | 18.0965 | 28.1740 |
| B2_prev_incumbent | 7.760696 | 6.133553 | 60.228403 | 0.7782 | 18.4729 | 27.4744 |
| B1_prev_v2 | 7.334318 | 5.753181 | 53.792220 | 0.7658 | 16.9933 | 26.1500 |
| pregame_v1 | 7.112517 | 5.577968 | 50.587896 | 0.7700 | 16.6529 | 25.3493 |

## Calendar-cluster sensitivity

Seed and all 7/14/28-day results are retained in the JSON. Season game weights stay fixed. Differences are candidate minus comparator.

| Variant | Block days | Contrast | RMSE difference | Exploratory 95% interval |
|---|---:|---|---:|---|
| as_frozen | 7 | pregame_v1-B0_home_only | -0.831579 | [-0.964537, -0.706377] |
| as_frozen | 7 | pregame_v1-B1_prev_v2 | -0.221801 | [-0.291171, -0.150727] |
| as_frozen | 7 | pregame_v1-B2_prev_incumbent | -0.648179 | [-0.784144, -0.518047] |
| as_frozen | 7 | B1_prev_v2-B2_prev_incumbent | -0.426378 | [-0.534566, -0.327884] |
| as_frozen | 14 | pregame_v1-B0_home_only | -0.831579 | [-0.985097, -0.689604] |
| as_frozen | 14 | pregame_v1-B1_prev_v2 | -0.221801 | [-0.303367, -0.143473] |
| as_frozen | 14 | pregame_v1-B2_prev_incumbent | -0.648179 | [-0.797851, -0.496523] |
| as_frozen | 14 | B1_prev_v2-B2_prev_incumbent | -0.426378 | [-0.540123, -0.314860] |
| as_frozen | 28 | pregame_v1-B0_home_only | -0.831579 | [-1.001979, -0.685501] |
| as_frozen | 28 | pregame_v1-B1_prev_v2 | -0.221801 | [-0.303059, -0.155468] |
| as_frozen | 28 | pregame_v1-B2_prev_incumbent | -0.648179 | [-0.764051, -0.547193] |
| as_frozen | 28 | B1_prev_v2-B2_prev_incumbent | -0.426378 | [-0.531431, -0.336427] |
| development_rescaled_post_hoc | 7 | pregame_v1-B0_home_only | -0.831360 | [-0.963872, -0.706600] |
| development_rescaled_post_hoc | 7 | pregame_v1-B1_prev_v2 | -0.221352 | [-0.290196, -0.150825] |
| development_rescaled_post_hoc | 7 | pregame_v1-B2_prev_incumbent | -0.358748 | [-0.453315, -0.262745] |
| development_rescaled_post_hoc | 7 | B1_prev_v2-B2_prev_incumbent | -0.137396 | [-0.190364, -0.082009] |
| development_rescaled_post_hoc | 14 | pregame_v1-B0_home_only | -0.831360 | [-0.984532, -0.689864] |
| development_rescaled_post_hoc | 14 | pregame_v1-B1_prev_v2 | -0.221352 | [-0.305301, -0.141303] |
| development_rescaled_post_hoc | 14 | pregame_v1-B2_prev_incumbent | -0.358748 | [-0.469730, -0.252619] |
| development_rescaled_post_hoc | 14 | B1_prev_v2-B2_prev_incumbent | -0.137396 | [-0.183173, -0.095817] |
| development_rescaled_post_hoc | 28 | pregame_v1-B0_home_only | -0.831360 | [-1.001378, -0.685557] |
| development_rescaled_post_hoc | 28 | pregame_v1-B1_prev_v2 | -0.221352 | [-0.308609, -0.147215] |
| development_rescaled_post_hoc | 28 | pregame_v1-B2_prev_incumbent | -0.358748 | [-0.476365, -0.253507] |
| development_rescaled_post_hoc | 28 | B1_prev_v2-B2_prev_incumbent | -0.137396 | [-0.188662, -0.092672] |

## Limits

- Holdout is spent; no fresh validation or model refit.
- Nonoverlapping calendar-cluster sensitivity does not resolve fitting uncertainty, recurrent-team dependence or new-season generalization.
- Track A uses realized participation; only Track B is operational pregame.
- Holdout calibration regressions/bins and existing subgroup flags are descriptive, not deployable routing rules.
- Accounting and regularisation changed jointly; no isolated accounting effect.
- Intervals are unadjusted exploratory comparisons; no multiplicity-controlled discovery claim.
