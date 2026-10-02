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

`source_data/` is an **empty submodule gitlink** (`88473250…`) whose remote is a
placeholder (`github.com/YOUR-ACCOUNT/ssac27-pmi-source-data.git`). It contains
no bytes and grants nothing. It is documented here so that its inert state is
explicit rather than mistaken for a working data repository. See `DATA.md`,
`README.md` (Reproduction levels), and gate G2 in `PUBLICATION_DECISION.md`.

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
2. Resolve or remove the `source_data` gitlink (gate G2).
3. Include prominent NBA.com attribution where permitted.
