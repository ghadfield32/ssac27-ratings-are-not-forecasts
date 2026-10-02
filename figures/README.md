# Figures

The paper's figures are generated from the tracked evaluation tables by
`make_figures.py` and are kept in a single place, `supplement/figures/`, so that
there is exactly one copy of each figure and no drift between locations.

This directory exists as the paper-level figure location. It intentionally holds
no duplicated bytes.

| Figure | Purpose | File |
|---|---|---|
| Figure 1 | Calibration and the rescaled gain ordering | `supplement/figures/fig1_calibration_and_gains.svg` (`.png`) |
| Figure 2 | Interval quality — width, coverage, and tail misses | `supplement/figures/fig2_interval_quality.svg` (`.png`) |

Regenerate with:

```bash
python make_figures.py
```

The abstract's single table is `table1.csv`. The abstract carries one table; the
manuscript carries the two figures above.
