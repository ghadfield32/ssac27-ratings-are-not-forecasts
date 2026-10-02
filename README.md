# Ratings Are Not Forecasts: Accounting, Calibration, and Information Timing in NBA Player-Impact Forecasting

Geoffrey Hadfield, World model Sports LLC (CEO/founder).

Local supporting-package revision for the SSAC27 abstract competition. **Not submitted or publication-cleared.** A public repository URL and a permissible data release are unresolved. No submission receipt is recorded.

This update accompanies the existing saved-forecast package. It adds a corrected abstract, a substantive manuscript draft, claim bindings, post hoc robustness analyses, figures and an explicit release checklist. It does not replace the saved predictions, original frozen parameters or expected results.

## Reproduce saved-forecast results

The existing package's `reproduce.py` needs numpy and pandas. A locked
environment is provided; run it from any directory with the package path:

```powershell
uv sync --frozen --extra dev --python 3.12
python path/to/package/reproduce.py
```

It checks the original pooled/per-season RMSE, coverage, paired game-bootstrap intervals and the previously executed development-only rescaling against `data/expected.json`. It must end with `OK: every value matches the committed results`.

Run this update's supplement without modifying the existing package:

```powershell
python supplement_analysis.py --package path/to/package --output path/to/output/supplement
```

The supplement validates both evaluation tables, refuses missing/inconsistent season, phase, game identity or calendar-year metadata, and binds its four input files to the exact reviewed SHA-256 values in `input_bindings.json` before writing results. It rechecks hashes after execution. The calendar-year check permits exceptional COVID schedules; exact dates are pinned by the byte binding, not inferred from a normal October-to-June calendar. It produces `supplement_results.json` and `SUPPLEMENT_RESULTS.md`. All analyses are labelled post hoc. It adds MSE/MAE, a proper 80% interval score, widths and tail misses, development-defined calibration bins, existing subgroup diagnostics, and 7/14/28-day calendar-cluster sensitivity. No rating model is fitted or promoted. Byte identity is not proof of historical information availability.

## Study boundary

The distributed synthetic regression suite runs with `python -m pytest test_supplement.py -q`. The executed author run passed all 14 tests. `requirements-dev.txt` records the test dependency; this observed environment has not been verified in a fresh clone or installed environment.

The operational target is home net points per 100 combined possessions, not an ordinary point spread. Track B projects participation using earlier team games. Track A uses realized participation and is diagnostic only. The original models and offsets were frozen before the 2023-24/2024-25 evaluation read. Every later recalibration, robustness analysis and manuscript revision is post hoc; those seasons are now exposed.

The legacy comparator is the authors' earlier implementation, not a public RAPM implementation. Accounting and regularisation changed together. Neither market superiority, coaching effects nor financial/operational returns were measured.

## Reproduction levels

1. **Saved forecasts to results:** executed and verified locally using the existing evaluation CSVs.
2. **Archived fitted runs to evaluation tables:** the existing `rebuild_tables.py` expects a complete source package that is not bundled. The placeholder submodule that used to sit at `source_data/` was removed in RC2 and replaced by `source_data/README.md`. On Oct. 1 a separate existing local source checkout at revision 88473250c289ff8019a9ae6a389107d6d12d98c3 was verified against all 11,959 manifest entries and used to reconstruct both 10,466-row, 20-column tables to tolerance 1e-9. Only the runner's SRC assignment was redirected in memory; its scientific functions and original files were unchanged. See LOCAL_SOURCE_RECONSTRUCTION.json. This closes local archived-fits-to-tables reconstruction, not anonymous public-clone or raw-only refit validation.
3. **Raw observations to refitted models and results:** not demonstrated by either command above. A future hermetic refit must pin inputs, code, settings, environment and exact output equivalence.

Do not run a submodule command expecting a working public data repository, or claim that an anonymized/derived release automatically satisfies rights or conference requirements. [DATA.md](DATA.md) specifies the boundary.

## Files in this revision

| File | Purpose |
|---|---|
| `abstract.md` | Submission candidate; title/body/table together must remain below 500 words |
| `MANUSCRIPT.md` | Evidence-bound manuscript draft; not a formatted full-paper submission |
| `CLAIM_LEDGER.md` | Exact evidence and limitation for each material claim |
| `PRIOR_WORK.md` | Closest primary precedents and permitted novelty wording |
| `DATA.md` | Data inventory, provenance and unresolved release decisions |
| `supplement_analysis.py` | Standalone saved-forecast diagnostics |
| `supplement/` | Executed supplemental results and figures |
| `FUTURE_STUDY_CONTRACT.md` | Controlled comparison and untouched future validation; unexecuted |
| `SUBMISSION_CHECKLIST.md` | Local checks and remaining operator/external gates |
| `AUTHORS.json` | Operator-supplied author metadata; public URL/receipt unset |

## Prior work

Ridge RAPM and out-of-sample testing precede this study (Sill, 2010). L-RAPM uses weekly expanding-window prediction for lineup/possession outcomes (Petridis and Pelechrinis, 2026). This paper's defensible contribution is a case study of accounting, forecast scale, participation information and comparison fairness, not the invention of those established methods. See [PRIOR_WORK.md](PRIOR_WORK.md).

## Publication

The current local package has no configured remote. Publication is a separate operator-controlled action after the exact payload, third-party data permissions and conference compliance are resolved. Include prominent NBA.com attribution where permitted. A code licence cannot grant rights to third-party data. The source-data placeholder and unsupported submitted/pinned-tag claims must be removed or replaced by verified facts before release.
