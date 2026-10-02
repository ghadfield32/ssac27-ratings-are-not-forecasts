# Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting

Geoffrey Hadfield, World Model Sports LLC (CEO/founder).

This is the public supporting repository for the SSAC27 abstract candidate. The reviewed release candidate is tag `ssac27-pmi-rc2-20261001` at commit `a5110b1190d18d30c378b9ef30f21d132ecf636a`. The repository has been anonymously cloned and its reported-statistics reproduction rerun successfully. **The paper has not been submitted to Sloan; no submission receipt exists.**

A standing data-rights risk remains open: the tracked evaluation tables are derived from NBA.com data, and this repository does not claim a redistribution licence for those derived tables. See [RIGHTS.md](RIGHTS.md), [DATA.md](DATA.md), and [PUBLICATION_DECISION.md](PUBLICATION_DECISION.md). Publication occurred on explicit operator authorization with that risk recorded rather than silently cleared.

## The question

Teams use player-impact ratings to compare players, but **a rating is not a forecast**. Turning one into a pregame game forecast also requires correct statistical units, an estimate of who will play, a calibrated forecast scale, and information that existed before tipoff. This study asks how much each of those choices changes the apparent value of an in-house rating model.

## The main result

An apparent large advantage from rebuilding the ratings **shrinks substantially** once forecast scale is audited, while the gain from weekly updating **survives**.

| Forecast | Original RMSE | Dev. slope (ideal 1) | Post-hoc rescaled RMSE |
|---|---:|---:|---:|
| Home court only | 7.944 | N/A | N/A |
| Prior-season legacy | 7.761 | 0.47 | 7.471 |
| Prior-season reconciled | 7.334 | 0.90 | 7.334 |
| Weekly reconciled | 7.113 | 1.00 | 7.113 |

*2,430 evaluation games; home margin per 100 combined possessions. Calibration slope is undefined for the constant home-court-only baseline. Lower RMSE is better; a slope near 1 indicates well-scaled forecasts.*

The legacy model was not merely less accurate — it was **badly scaled**. Rescaling on development seasons only moves it from 7.761 to 7.471, cutting its disadvantage against the reconciled model from about 0.43 to 0.14 RMSE. Weekly updating still adds 0.22. Calibration therefore reverses which component appears more important, which is the paper's central claim.

## Read the paper

| Artifact | Purpose |
|---|---|
| [abstract.txt](abstract.txt) | Plain-text abstract, exact submission source |
| [abstract.md](abstract.md) | Rendered abstract with the table |
| [MANUSCRIPT.md](MANUSCRIPT.md) | Evidence-bound manuscript |
| [CLAIM_LEDGER.md](CLAIM_LEDGER.md) | Every claim mapped to its evidence and limitation |
| [PRIOR_WORK.md](PRIOR_WORK.md) | Nearest prior work and the novelty boundary |

## Release state

The repository is public under explicit operator authorization. **The paper has not been submitted to Sloan; no submission receipt exists.** The reviewed snapshot is tag `ssac27-pmi-rc2-20261001` (`a5110b11`). A reviewed abstract revision is tagged `ssac27-abstract-submission-20261001` (`0afe1de4`); the abstract has since been reframed for readability and that reframe has **not** yet had its own independent review — see [RELEASE_CANDIDATE.json](RELEASE_CANDIDATE.json).

A standing data-rights risk remains open: the tracked evaluation tables are derived from NBA.com data, and this repository does not claim a redistribution licence for them. See [RIGHTS.md](RIGHTS.md), [DATA.md](DATA.md), and [PUBLICATION_DECISION.md](PUBLICATION_DECISION.md). Publication occurred on explicit operator authorization with that risk recorded rather than silently cleared.

## What this repository supports

The package reproduces the saved-forecast results reported in the abstract and the post hoc robustness supplement. It does not claim a raw-source refit, betting-market superiority, coaching effects, or financial/operational returns.

## Reproduce the reported results

Use Python 3.12 and the locked environment:

```powershell
uv sync --frozen --extra dev --python 3.12
python reproduce.py
python supplement_analysis.py --package . --output ./tmp/supplement
python -m pytest test_supplement.py -q -p no:cacheprovider
```

`reproduce.py` must finish with `OK: every value matches the committed results`. The supplement validates the bound inputs before and after analysis, and the test suite contains 14 regression checks. See [REPRODUCTION_RECEIPT.json](REPRODUCTION_RECEIPT.json).

## Study boundary

The operational target is home net points per 100 combined possessions, not an ordinary point spread. Track B projects participation from earlier team games; Track A uses realized participation and is diagnostic. The original models and offsets were frozen before the 2023-24/2024-25 evaluation read. Later recalibration, robustness analysis, and manuscript revisions are post hoc; those seasons are now exposed.

The legacy comparator is the author's earlier implementation, not a public RAPM implementation. Possession accounting and regularisation changed together, so the paper does not attribute their full difference to accounting alone.

## Reproduction levels

1. **Saved forecasts to reported statistics — executed.** Uses the tracked evaluation tables and frozen parameters.
2. **Archived fitted runs to evaluation tables — executed locally, not from this public source alone.** See [LOCAL_SOURCE_RECONSTRUCTION.json](LOCAL_SOURCE_RECONSTRUCTION.json).
3. **Raw observations to refitted models and results — not demonstrated.** Do not infer this from the presence of pipeline source code.

## Data and rights

Tracked evaluation tables are included because they are required for the public L1 replay. They are derived from NBA.com data and contain no raw play-by-play, rotations, lineup stints, bulk box scores, or player-level provider tables. Their redistribution status is **not claimed to be cleared**. Read [RIGHTS.md](RIGHTS.md) before reusing or redistributing them.

## Review trail

- Exact reviewed RC2 tag: `ssac27-pmi-rc2-20261001`
- Exact abstract submission snapshot: `ssac27-abstract-submission-20261001` → `0afe1de4bef1700a613d26cd3970bf4b7464aed8`
- Focused review of the revised abstract: **APPROVE — zero BLOCKER/MAJOR**
- Independent review record: [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md)
- Release review and remediation: [REVIEW.md](REVIEW.md)
- Claim bindings: [CLAIM_LEDGER.md](CLAIM_LEDGER.md)
- Prior-work comparison: [PRIOR_WORK.md](PRIOR_WORK.md)
- Release state: [RELEASE_STATUS.yaml](RELEASE_STATUS.yaml)

## Submission status

**Not submitted.** The public repository and anonymous reproduction are complete; Sloan submission remains a separate operator action. Use [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) before filing the form.
