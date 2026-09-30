"""
RapmPipelineConfig -- all paths, hyperparameters, and quality thresholds
for the Luck-Adjusted RAPM (LA-RAPM) pipeline.

All paths derived from PROJECT_ROOT. No hardcoded absolute paths.
No fallback values -- missing data raises errors.

Standard RAPM reference:
  lambda_reg in [2000, 5000], multi-season pooling with time decay,
  possession-weighted, sparse design matrix, net_rating_per_100 target.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
DATA_ROOT = PROJECT_ROOT / "api" / "src" / "airflow_project" / "data"
CACHE_ROOT = PROJECT_ROOT / "cache"
PIPELINE_DIR = Path(__file__).resolve().parent


@dataclass
class RapmPipelineConfig:
    """Configuration for the LA-RAPM pipeline."""

    PRIOR_MODES = ("date_censored", "lagged", "same_season")

    # -- Project paths ---------------------------------------------------
    project_root: Path = PROJECT_ROOT
    data_root: Path = DATA_ROOT
    pipeline_dir: Path = PIPELINE_DIR

    # -- Regularization --------------------------------------------------
    lambda_reg: float = 2500.0           # Standard RAPM range: 2000-5000
    fit_intercept: bool = True           # Absorbs league-average scoring

    # -- Multi-season pooling --------------------------------------------
    seasons_back: int = 3                # Pool N seasons for more stable estimates
    decay_factor: float = 0.80           # Per-season time decay (most recent = 1.0)

    # -- Stint quality filters -------------------------------------------
    min_poss_per_stint: int = 3          # Minimum possessions to include stint
    min_players_per_lineup: int = 5      # Must be 5v5

    # -- Player quality filters ------------------------------------------
    min_poss_per_player: int = 200       # Minimum possessions for a player to keep

    # -- Input paths -----------------------------------------------------
    possessions_path: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "possessions.parquet"
    )
    play_by_play_linked_path: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "play_by_play_linked_stints.parquet"
    )
    rotation_stints_path: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "game_rotation_player_stint.parquet"
    )
    gold_psf_path: Path = field(
        default_factory=lambda: DATA_ROOT / "gold" / "features" / "player_season_features.parquet"
    )
    player_bio_path: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "dims" / "player_bio_unified.parquet"
    )
    game_dim_path: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "dims" / "game_dim.parquet"
    )

    # -- Output paths ----------------------------------------------------
    stints_output_path: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "rapm_stints.parquet"
    )
    rapm_by_season_dir: Path = field(
        default_factory=lambda: CACHE_ROOT / "features" / "rapm_by_season"
    )
    rapm_multi_season_path: Path = field(
        default_factory=lambda: CACHE_ROOT / "features" / "la_rapm_multi_season.parquet"
    )
    # Offense/defense split RAPM output
    rapm_od_path: Path = field(
        default_factory=lambda: CACHE_ROOT / "features" / "la_rapm_od.parquet"
    )
    # On-Off differential output
    on_off_path: Path = field(
        default_factory=lambda: CACHE_ROOT / "features" / "player_on_off_diff.parquet"
    )
    # Per-season intermediate files
    possessions_by_season_dir: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "possessions_by_season"
    )
    linked_events_by_season_dir: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "linked_events_by_season"
    )
    stints_by_season_dir: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "rapm_stints_by_season"
    )
    # Luck-adjusted stints (from build_luck_neutral_stints.py)
    la_stints_by_season_dir: Path = field(
        default_factory=lambda: DATA_ROOT / "silver" / "nba" / "supplements" / "rapm_stints_la_by_season"
    )
    pbp_bronze_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "bronze" / "nba" / "play_by_play"
    )

    # -- Calibration / schemas -------------------------------------------
    calibration_path: Path = field(
        default_factory=lambda: PIPELINE_DIR / "calibration" / "rapm_config_v1.json"
    )
    schema_path: Path = field(
        default_factory=lambda: PIPELINE_DIR / "schemas" / "rapm_pipeline.yaml"
    )

    # -- EDA output ------------------------------------------------------
    eda_output_dir: Path = field(
        default_factory=lambda: CACHE_ROOT / "eda" / "rapm"
    )

    # -- Validation thresholds -------------------------------------------
    min_bpm_correlation: float = 0.30    # r(RAPM_NET, BPM_BBREF) for MP >= 2000
    min_stints_per_season: int = 50_000  # Expected stint count per season

    # -- Season list (all seasons with PBP data) -------------------------
    available_seasons: List[str] = field(default_factory=lambda: [
        "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
        "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26",
    ])

    def validate_prior_mode(self, prior_mode: str) -> str:
        """Validate the requested shooting-prior mode."""
        if prior_mode not in self.PRIOR_MODES:
            raise ValueError(
                f"Unsupported prior_mode={prior_mode}. "
                f"Expected one of {self.PRIOR_MODES}."
            )
        return prior_mode

    def previous_available_season(self, season: str) -> str:
        """Return the immediately preceding available season."""
        seasons = list(self.available_seasons)
        if season not in seasons:
            raise ValueError(f"Unknown season: {season}")
        idx = seasons.index(season)
        if idx == 0:
            raise ValueError(
                f"No previous season available for {season}. "
                "Lagged priors require at least one prior season."
            )
        return seasons[idx - 1]

    def supported_prior_target_seasons(
        self,
        prior_mode: str,
        seasons: List[str] | None = None,
    ) -> List[str]:
        """Return target seasons supported by the requested prior mode."""
        prior_mode = self.validate_prior_mode(prior_mode)
        candidate_seasons = list(seasons or self.available_seasons)
        if prior_mode == "same_season":
            return candidate_seasons
        if not candidate_seasons:
            return []

        first_available = self.available_seasons[0]
        return [season for season in candidate_seasons if season != first_available]

    def shooting_priors_path(self, prior_mode: str = "date_censored") -> Path:
        """Return the canonical shooting-priors artifact path for a mode."""
        prior_mode = self.validate_prior_mode(prior_mode)
        if prior_mode == "date_censored":
            return CACHE_ROOT / "features" / "player_shooting_priors.parquet"
        if prior_mode == "lagged":
            return CACHE_ROOT / "features" / "player_shooting_priors_lagged.parquet"
        return CACHE_ROOT / "features" / "player_shooting_priors_same_season.parquet"

    def la_stints_dir(self, prior_mode: str = "date_censored") -> Path:
        """Return the canonical luck-adjusted stints directory for a mode."""
        prior_mode = self.validate_prior_mode(prior_mode)
        if prior_mode == "date_censored":
            return self.la_stints_by_season_dir
        if prior_mode == "lagged":
            return self.stints_by_season_dir.parent / "rapm_stints_la_lagged_by_season"
        return self.stints_by_season_dir.parent / "rapm_stints_la_same_season_by_season"

    def rapm_od_path_for_mode(self, prior_mode: str = "date_censored") -> Path:
        """Return the OD RAPM artifact path for a mode."""
        prior_mode = self.validate_prior_mode(prior_mode)
        if prior_mode == "date_censored":
            return self.rapm_od_path
        if prior_mode == "lagged":
            return self.rapm_od_path.parent / "la_rapm_od_lagged.parquet"
        return self.rapm_od_path.parent / "la_rapm_od_same_season.parquet"
