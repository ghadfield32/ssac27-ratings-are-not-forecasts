"""
LA-RAPM Pipeline -- Luck-Adjusted Regularized Adjusted Plus-Minus
=================================================================

Replaces the broken RAPM implementation (r=-0.06 vs BPM) with a proper
multi-season, possession-weighted, sparse Ridge regression approach.

Calibration params: rapm_pipeline/calibration/rapm_config_v*.json
Primary scripts:
  scripts/fit_la_rapm.py          -- fit RAPM model (per-season or multi-season)
  scripts/merge_la_rapm_to_gold.py -- merge RAPM into Gold PSF
  scripts/run_rapm_eda.py         -- pre-fit EDA analysis

Key fixes over old RAPM:
  - lambda=2500 (was 100, causing massive overfitting)
  - net_rating_per_100 target (was raw points_scored)
  - scipy.sparse.csr_matrix (was dense np.zeros)
  - Merge on [PLAYER_ID, SEASON] (was PLAYER_ID only)
  - Multi-season pooling with time decay
  - Possession-weighted Ridge regression

Version history:
  v1 (2026-02-20): Initial LA-RAPM implementation.
                    Multi-season pooling, sparse design matrix, possession weighting.
"""
from pathlib import Path
import json

RAPM_PIPELINE_DIR = Path(__file__).parent
CALIBRATION_DIR = RAPM_PIPELINE_DIR / "calibration"
SCHEMAS_DIR = RAPM_PIPELINE_DIR / "schemas"

# Re-export public API
from .config import RapmPipelineConfig
from .main import RapmPipeline


def load_rapm_config(version: int = 1) -> dict:
    """Load RAPM calibration parameters.

    Parameters
    ----------
    version : int
        Version number for rapm_config_v{version}.json.

    Returns
    -------
    dict with calibration parameters.
    """
    path = CALIBRATION_DIR / f"rapm_config_v{version}.json"
    assert path.exists(), f"RAPM config not found: {path}"
    with open(path) as f:
        return json.load(f)


def load_rapm_results(multi_season: bool = True) -> "pd.DataFrame":
    """Load the latest RAPM results.

    Parameters
    ----------
    multi_season : bool
        If True, load the canonical multi-season net RAPM artifact.
        Else load the latest per-season artifact.

    Returns
    -------
    pd.DataFrame with PLAYER_ID, SEASON, RAPM_NET columns.
    """
    import pandas as pd
    config = RapmPipelineConfig()

    if multi_season:
        path = config.rapm_multi_season_path
    else:
        # Find latest per-season file
        season_dir = config.rapm_by_season_dir
        assert season_dir.exists(), f"No per-season RAPM found: {season_dir}"
        files = sorted(season_dir.glob("*.parquet"))
        assert files, f"No parquet files in {season_dir}"
        path = files[-1]

    assert path.exists(), f"RAPM results not found: {path}. Run fit_la_rapm.py first."
    return pd.read_parquet(path)
