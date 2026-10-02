# Third-party notices and attribution

## Scope

This file covers third-party material in this package. `LICENSE` (MIT) covers
**the authors' original code only**. It does not grant, extend, or imply any
right to third-party data.

## Statistics and derived content

Statistics underlying this study originate from **NBA.com**.

The per-game evaluation tables and the forecasts in them are *derived research
artifacts*, not raw provider data. They are included here because they are the
minimum input needed to independently recompute the reported statistics. Their
inclusion is **attribution, not a licence**, and it is the subject of gate G1 in
`PUBLICATION_DECISION.md`.

Nothing in this package should be read as a claim of permission to redistribute
NBA.com content or content derived from it.

## Upstream source data

Raw play-by-play, box scores, rotations and player-level provider tables are
**not** part of this package and are not redistributed here.

A broken placeholder submodule pointer previously existed at `source_data/`: an
empty gitlink whose remote pointed at a nonexistent placeholder repository, not
at any real data source. It has been **removed** in RC2. `source_data/README.md`
now documents what upstream categories were used privately, why they are not
bundled, and which reproduction level this package actually supports. There is no
submodule here.

## Methodological precedents

Ridge RAPM and out-of-sample testing precede this work (Sill, 2010). L-RAPM uses
weekly expanding-window prediction (Petridis and Pelechrinis, 2026). See
`PRIOR_WORK.md` for the closest-primary-work comparison and the permitted
novelty wording. These are cited precedents, not redistributed material.

## Not evaluated

Betting-market data and operational decision benefits were **not** evaluated.
No market-comparison implication is made or implied.

## Required action before publication

1. Resolve gate G1: either obtain permission, or publish only what a permitted
   derived-evaluation release allows, with the reproduction limit stated.
2. Include prominent NBA.com attribution where permitted.

(Gate G2, the broken `source_data` gitlink, was resolved in RC2 by removing it.)
