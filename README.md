# Ratings Are Not Forecasts: A Past-Only Test of NBA Player-Impact Models

Supporting repository for an abstract submitted to the MIT Sloan Sports Analytics Conference 2027 research paper competition.

## Reproduce the paper's numbers (about one minute)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
.venv/bin/python reproduce.py
```

`reproduce.py` rebuilds Table 1 and every figure in the abstract from `data/`. It checks each value against the committed results in `data/expected.json` and exits non-zero on any mismatch. Expected output ends with `OK: every value matches the committed results`.

## What the study is

**Question.** We rebuilt NBA possession accounting from play-by-play so that credited points equal box-score points in every admitted game. We then tested four pregame forecasts of each game's home margin per 100 combined possessions, using only information available before tip-off:
- home court alone;
- prior-season ratings from our earlier in-house build, which counted play-by-play rows as possessions;
- prior-season reconciled ratings;
- reconciled ratings refit weekly from past games only.

**Design.** The evaluation contract, the development results and the frozen parameters were committed before a single read of 2,430 held-out games (2023-24 and 2024-25). This is a historical past-only replay, not an archive of live forecasts.

**Post hoc.** The development-only rescaling of every rating-based model was added after the holdout read. It is reported as post hoc.

**Not claimed.** No comparison with betting markets. No causal claim. No claim about public RAPM implementations: the legacy comparator is our own earlier build.

## Layout

| Path | Contents |
|---|---|
| `reproduce.py` | the quick command; needs numpy and pandas only |
| `data/` | per-game evaluation tables and frozen parameters; see [DATA.md](DATA.md) |
| `source_data/` | git submodule: the NBA.com source data and derived runs the tables are built from |
| `rebuild_tables.py` | regenerates `data/*.csv` from `source_data/` and requires an exact match |
| `pipeline/` | the code, as of evaluation commit `e3140577b`, that built the possession ledger, fitted the ratings and produces the tables |
| `abstract.md` | the submitted abstract |

## Where the numbers come from

```bash
git clone --recurse-submodules <this repository>
python rebuild_tables.py        # source_data/ -> data/*.csv, checked to 1e-9 (needs requirements-rebuild.txt)
python reproduce.py             # data/*.csv -> every number in the abstract
```

## Licence

- Code: MIT (see `LICENSE`).
- Data: NBA.com statistics and tables derived from them; see [DATA.md](DATA.md) and `source_data/README.md` for attribution and terms.

## Relation to prior work

**Sill, "Improved NBA Adjusted +/- Using Regularization and Out-of-Sample Testing" (SSAC 2010)** established ridge-regularised adjusted plus-minus and its out-of-sample evaluation. That evaluation trained through February and tested on March and April of 2008-09, and scored held-out games using the lineups and possessions that actually occurred.

This study does not claim either contribution. It adds:
1. **Genuinely pregame forecasts.** Participation is projected from past games (Track B). Track A, with observed participation, is Sill's information class and is reported only as a diagnostic.
2. **Reconciled possession accounting**, and a measured scale failure (legacy calibration slope 0.47) when possessions are not reconciled.
3. **Explicit development-only calibration.**
4. **A frozen evaluation** across two full held-out seasons, with paired intervals.
