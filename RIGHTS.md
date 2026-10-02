# Rights and data disposition — PMI

**Status: NOT PUBLICATION-CLEARED.** Gate G1 is open.

This file is the in-package authority for the rights statement that
`PUBLICATION_DECISION.md`, `RELEASE_STATUS.yaml`, `DATA_INVENTORY.json` and
`source_data/README.md` refer to. It records what is known and what is decided;
it does **not** grant permission.

## What is asserted, and what is not

| Statement | State |
|---|---|
| The authors' original code is MIT-licensed | Yes — see `LICENSE`. Covers **original code only**. |
| Statistics underlying the study originate from NBA.com | Yes — attribution, recorded in `DATA.md`. |
| The tracked evaluation tables are NBA.com-derived | Yes — see `DATA_INVENTORY.json`. |
| A licence has been obtained to redistribute NBA.com-derived content | **No. Not asserted, not claimed.** |
| Academic intent, author affiliation, or anonymization grants redistribution rights | **No. Explicitly not inferred.** |
| A code licence can grant third-party data rights | **No.** |
| Publication is cleared | **No.** |

## The four files this gates

| File | Why it needs a decision |
|---|---|
| `data/pmi_games_track_a.csv` | Derived from NBA.com play-by-play/box. 10,466 rows. |
| `data/pmi_games_track_b.csv` | Same provenance. 10,466 rows. |
| `data/frozen_parameters.json` | Derived numeric constants; no provider rows. |
| `data/expected.json` | Derived summary values; no provider rows. |

Everything else tracked is original WMS code, authored documentation, or
generated output with no third-party row content.

## What is deliberately not bundled

Raw play-by-play, raw rotations and lineup stints, bulk box scores, and
player-level provider tables. See `source_data/README.md` and
`THIRD_PARTY_NOTICES.md`.

## The decision that is required

The operator must choose one of:

1. **Permitted derived-evaluation release.** Publish the derived per-game tables
   with the reproduction limit stated, subject to the conference accepting that
   scope.
2. **Permission-cleared source/refit release.** Obtain actual third-party
   permission and publish the full chain.
3. **Keep the submission blocked.** The correct outcome if neither clears.

There is no fourth option in which the question resolves itself. No permission
is inferred from academic intent, affiliation, de-identification, or the code
licence.

## Ownership of the decision

This is the operator's decision, not an engineering one. The candidate records
it as open; it does not guess. See `PUBLICATION_DECISION.md` for the gate and
`DATA_INVENTORY.json` for the per-file inventory.
