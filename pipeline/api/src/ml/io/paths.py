# api/src/ml/io/paths.py
"""
SINGLE SOURCE OF TRUTH for all data pipeline paths.

This module centralizes all file paths for the Bronze-Silver-Gold data architecture.
All other modules should import from here rather than defining their own paths.

ARCHITECTURE:
    bronze/          # Raw immutable data (audit trail, scraped data - NOT API pulls)
    silver/          # Standardized canonical facts/dims/supplements
        nba/
            facts/       # Core fact tables (player_game, team_game, player_season, etc.)
            dims/        # Dimension tables (player_dim, team_dim, game_dim, calendar_dim)
            supplements/ # Supporting data (contracts, synergy, bbref_defense, est_metrics)
    gold/            # ML-ready outputs
        features/    # Engineered features (rolling, lag, trend - still keyed like facts)
        products/    # Final ML products (combined features + supplements for specific use cases)

NAMING CONVENTIONS:
    facts:       {granularity}_fact.parquet (e.g., player_game_fact.parquet)
    dims:        {entity}_dim.parquet (e.g., player_dim.parquet)
    supplements: {source}_{granularity}.parquet (e.g., contracts_player_season.parquet)
    features:    {granularity}_features.parquet (e.g., player_game_features.parquet)
    products:    {use_case}_{granularity}.parquet (e.g., player_value_day.parquet)

CANONICAL GOLD PRODUCT PATH (2026-06-19):
    `gold/products` is the ONE canonical directory for final ML products. The
    historical `gold/marts` symlink alias has been eliminated entirely — there
    is no runtime alias and no defensive fallback. `validate_gold_layout()`
    fails fast if the canonical directory is missing, is a dangling symlink, or
    resolves outside DATA_ROOT.

Created: 2026-02-03
"""

from pathlib import Path
from typing import Dict, Optional
import os


def _find_api_root() -> Path:
    """Find the 'api' (or 'app') root directory containing src/ml.

    Uses __file__ rather than os.getcwd() so resolution is stable regardless
    of the calling process's working directory (Airflow, Railway, local scripts).
    paths.py lives at api/src/ml/io/paths.py, so parents[3] is the api root.
    """
    # Fast path: canonical location — parents[3] from api/src/ml/io/paths.py
    candidate = Path(__file__).resolve().parents[3]
    if (candidate / "src" / "ml").exists():
        return candidate

    # Fallback: walk up from this file for non-standard install layouts
    for parent in Path(__file__).resolve().parents:
        for name in ("api", "app"):
            p = parent / name
            if p.exists() and (p / "src" / "ml").exists():
                return p

    raise FileNotFoundError(
        f"Could not locate api/src/ml relative to {Path(__file__).resolve()}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ROOT PATHS
# ══════════════════════════════════════════════════════════════════════════════

API_ROOT = _find_api_root()
DATA_ROOT = API_ROOT / "src" / "airflow_project" / "data"
ML_DATA_ROOT = API_ROOT / "src" / "ml" / "data"

# Layer roots
SILVER_ROOT = DATA_ROOT / "silver" / "nba"
GOLD_ROOT = DATA_ROOT / "gold"

# Sub-layer roots
SILVER_FACTS_ROOT = SILVER_ROOT / "facts"
SILVER_DIMS_ROOT = SILVER_ROOT / "dims"
SILVER_SUPPLEMENTS_ROOT = SILVER_ROOT / "supplements"
GOLD_FEATURES_ROOT = GOLD_ROOT / "features"
GOLD_PRODUCTS_ROOT = GOLD_ROOT / "products"

# Registry and manifests
REGISTRY_ROOT = DATA_ROOT / "registry"
MANIFESTS_ROOT = DATA_ROOT / "manifests"
AUDIT_ROOT = DATA_ROOT / "audit"


# ══════════════════════════════════════════════════════════════════════════════
# SILVER LAYER - FACTS
# ══════════════════════════════════════════════════════════════════════════════

SILVER_FACTS: Dict[str, Path] = {
    # Core NBA API facts (from main_multi_level.py)
    "PLAYER_GAME": SILVER_FACTS_ROOT / "player_game_fact.parquet",
    "PLAYER_SEASON": SILVER_FACTS_ROOT / "player_season_fact.parquet",
    "PLAYER_TEAM_SEASON": SILVER_FACTS_ROOT / "player_team_season_fact.parquet",
    "TEAM_GAME": SILVER_FACTS_ROOT / "team_game_fact.parquet",
    "TEAM_SEASON": SILVER_FACTS_ROOT / "team_season_fact.parquet",
}


# ══════════════════════════════════════════════════════════════════════════════
# SILVER LAYER - DIMENSIONS
# ══════════════════════════════════════════════════════════════════════════════

SILVER_DIMS: Dict[str, Path] = {
    "PLAYER": SILVER_DIMS_ROOT / "player_dim.parquet",
    "TEAM": SILVER_DIMS_ROOT / "team_dim.parquet",
    "GAME": SILVER_DIMS_ROOT / "game_dim.parquet",
    "CALENDAR": SILVER_DIMS_ROOT / "calendar_dim.parquet",
}


# ══════════════════════════════════════════════════════════════════════════════
# SILVER LAYER - SUPPLEMENTS (Supporting data joined to facts)
# ══════════════════════════════════════════════════════════════════════════════

SILVER_SUPPLEMENTS: Dict[str, Path] = {
    # Contracts data (from spotrac/contracts pipeline)
    "CONTRACTS_PLAYER_SEASON": SILVER_SUPPLEMENTS_ROOT / "contracts_player_season.parquet",

    # Synergy playtype data
    "SYNERGY_PLAYER_SEASON": SILVER_SUPPLEMENTS_ROOT / "synergy_player_season.parquet",

    # Basketball-Reference defensive stats (Regular Season)
    "BBREF_DEFENSE_PLAYER_SEASON": SILVER_SUPPLEMENTS_ROOT / "bbref_defense_player_season.parquet",

    # Basketball-Reference playoff advanced stats (Session 427)
    "BBREF_PLAYOFF_ADVANCED_PLAYER_SEASON": SILVER_SUPPLEMENTS_ROOT / "bbref_playoff_advanced_player_season.parquet",

    # NBA estimated metrics
    "EST_METRICS_PLAYER_SEASON": SILVER_SUPPLEMENTS_ROOT / "est_metrics_player_season.parquet",

    # Injury data (expanded to daily level with resolved player IDs)
    "INJURY_EVENTS": SILVER_SUPPLEMENTS_ROOT / "injury_events.parquet",
    "INJURY_PLAYER_DAY": SILVER_SUPPLEMENTS_ROOT / "injury_player_day.parquet",
    "INJURY_PLAYER_SEASON": SILVER_SUPPLEMENTS_ROOT / "injury_player_season.parquet",

    # Team standings (derived from team_game_fact WIN_LOSS, Session 364)
    "TEAM_STANDINGS_SEASON": SILVER_SUPPLEMENTS_ROOT / "team_standings_season.parquet",

    # Game rotation stint data (from NBA API GameRotation endpoint, Session 364)
    "GAME_ROTATION_PLAYER_STINT": SILVER_SUPPLEMENTS_ROOT / "game_rotation_player_stint.parquet",
}


# ══════════════════════════════════════════════════════════════════════════════
# GOLD LAYER - FEATURES (engineered from Silver facts)
# ══════════════════════════════════════════════════════════════════════════════

GOLD_FEATURES: Dict[str, Path] = {
    "PLAYER_GAME": GOLD_FEATURES_ROOT / "player_game_features.parquet",
    "PLAYER_SEASON": GOLD_FEATURES_ROOT / "player_season_features.parquet",
    "PLAYER_TEAM_SEASON": GOLD_FEATURES_ROOT / "player_team_season_features.parquet",
    "TEAM_GAME": GOLD_FEATURES_ROOT / "team_game_features.parquet",
    "TEAM_SEASON": GOLD_FEATURES_ROOT / "team_season_features.parquet",
}


# ══════════════════════════════════════════════════════════════════════════════
# GOLD LAYER - PRODUCTS (ML-ready products combining features + supplements)
# ══════════════════════════════════════════════════════════════════════════════

GOLD_PRODUCTS: Dict[str, Path] = {
    # Player value prediction (daily granularity) -- REBUILD TARGET (P1)
    "PLAYER_VALUE_DAY": GOLD_PRODUCTS_ROOT / "player_value_day.parquet",

    # Player archetype/role assignments by season -- REBUILD TARGET (P0)
    "ARCHETYPE_HISTORY_SEASON": GOLD_PRODUCTS_ROOT / "archetype_history_season.parquet",

    # Team inventory/needs analysis
    "TEAM_INVENTORY_SEASON": GOLD_PRODUCTS_ROOT / "team_inventory_season.parquet",

    # Coach preferences
    "COACH_PREFERENCES_SEASON": GOLD_PRODUCTS_ROOT / "coach_preferences_season.parquet",

    # Team needs analysis (Session 364)
    "TEAM_NEEDS_SEASON": GOLD_PRODUCTS_ROOT / "team_needs_season.parquet",

    # Coach game-level profiles (Session 364)
    "COACH_GAME_PROFILES": GOLD_PRODUCTS_ROOT / "coach_game_profiles.parquet",

    # Coach season-level profiles (Session 364)
    "COACH_SEASON_PROFILES": GOLD_PRODUCTS_ROOT / "coach_season_profiles.parquet",

    # Coach clusters (Session 364)
    "COACH_CLUSTERS": GOLD_PRODUCTS_ROOT / "coach_clusters.parquet",

    # S6: Historical trade BPM outcomes (Session 616)
    "TRADE_OUTCOMES": GOLD_PRODUCTS_ROOT / "trade_outcomes.parquet",
}


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY PATHS (for migration reference - DO NOT USE for new code)
# ══════════════════════════════════════════════════════════════════════════════

LEGACY_PATHS: Dict[str, Path] = {
    # Old nba_api_data_pull locations
    "player_game_master": DATA_ROOT / "nba_api_data_pull" / "player_game_master.parquet",
    "player_season_master": DATA_ROOT / "nba_api_data_pull" / "player_season_master.parquet",
    "player_team_season_master": DATA_ROOT / "nba_api_data_pull" / "player_team_season_master.parquet",
    "team_game_master": DATA_ROOT / "nba_api_data_pull" / "team_game_master.parquet",

    # Old merged_final_dataset locations
    "contracts_master": DATA_ROOT / "merged_final_dataset" / "contracts_master.parquet",
    "injury_master": DATA_ROOT / "merged_final_dataset" / "injury_master.parquet",
    "synergy_playtype": DATA_ROOT / "merged_final_dataset" / "synergy_playtype_for_main_system.parquet",
    "defensive_stats_bbref": DATA_ROOT / "merged_final_dataset" / "defensive_stats_master_bbref_nba.parquet",
    "est_metrics": DATA_ROOT / "merged_final_dataset" / "player_estimated_metrics_all_seasons.parquet",

    # Old engineered file locations
    "player_game_engineered": DATA_ROOT / "merged_final_dataset" / "player_game_engineered.parquet",
    "player_season_engineered": DATA_ROOT / "merged_final_dataset" / "player_season_engineered.parquet",
    "player_team_season_engineered": DATA_ROOT / "merged_final_dataset" / "player_team_season_engineered.parquet",
    "team_game_engineered": DATA_ROOT / "merged_final_dataset" / "team_game_engineered.parquet",

    # Broken files (to be deprecated)
    "final_merged_player_game_BROKEN": DATA_ROOT / "merged_final_dataset" / "final_merged_player_game.parquet",
}


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION ARTIFACTS
# ══════════════════════════════════════════════════════════════════════════════

VALIDATION_ARTIFACTS: Dict[str, Path] = {
    "silver_manifest": MANIFESTS_ROOT / "silver_manifest.json",
    "gold_manifest": MANIFESTS_ROOT / "gold_manifest.json",
    "validation_log": AUDIT_ROOT / "validation_log.json",
    "migration_log": AUDIT_ROOT / "migration_log.json",
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_silver_fact_path(granularity: str) -> Path:
    """Get Silver fact path for a given granularity."""
    key = granularity.upper().replace("-", "_")
    if key not in SILVER_FACTS:
        raise KeyError(f"Unknown granularity: {granularity}. Valid: {list(SILVER_FACTS.keys())}")
    return SILVER_FACTS[key]


def get_silver_dim_path(entity: str) -> Path:
    """Get Silver dimension path for a given entity."""
    key = entity.upper()
    if key not in SILVER_DIMS:
        raise KeyError(f"Unknown dimension: {entity}. Valid: {list(SILVER_DIMS.keys())}")
    return SILVER_DIMS[key]


def get_silver_supplement_path(name: str) -> Path:
    """Get Silver supplement path by name."""
    key = name.upper().replace("-", "_")
    if key not in SILVER_SUPPLEMENTS:
        raise KeyError(f"Unknown supplement: {name}. Valid: {list(SILVER_SUPPLEMENTS.keys())}")
    return SILVER_SUPPLEMENTS[key]


def get_gold_feature_path(granularity: str) -> Path:
    """Get Gold feature path for a given granularity."""
    key = granularity.upper().replace("-", "_")
    if key not in GOLD_FEATURES:
        raise KeyError(f"Unknown granularity: {granularity}. Valid: {list(GOLD_FEATURES.keys())}")
    return GOLD_FEATURES[key]


def get_gold_product_path(product_name: str) -> Path:
    """Get Gold product path by name."""
    key = product_name.upper().replace("-", "_")
    if key not in GOLD_PRODUCTS:
        raise KeyError(f"Unknown product: {product_name}. Valid: {list(GOLD_PRODUCTS.keys())}")
    return GOLD_PRODUCTS[key]


# Every directory the pipeline owns and is allowed to create/write under DATA_ROOT.
# Single source of truth for both ensure_directories_exist() and validate_gold_layout().
MANAGED_DIRECTORIES = (
    SILVER_FACTS_ROOT,
    SILVER_DIMS_ROOT,
    SILVER_SUPPLEMENTS_ROOT,
    GOLD_FEATURES_ROOT,
    GOLD_PRODUCTS_ROOT,
    REGISTRY_ROOT,
    MANIFESTS_ROOT,
    AUDIT_ROOT,
)


def ensure_directories_exist() -> None:
    """Create all required directories if they don't exist.

    Runs validate_gold_layout() first so a misconfigured path (e.g. a stray
    symlink left by an old fleet bootstrap) fails loudly instead of being
    silently mkdir'd. Note `Path.mkdir(exist_ok=True)` does NOT suppress the
    error for a *dangling symlink* — the contract check below catches that case
    explicitly before we ever call mkdir.
    """
    validate_gold_layout()
    for d in MANAGED_DIRECTORIES:
        d.mkdir(parents=True, exist_ok=True)


def validate_gold_layout() -> None:
    """Fail-fast contract for the managed data layout.

    Raises RuntimeError if any managed directory path is occupied by something
    that is not a real, in-tree directory:

      * a dangling symlink (target does not resolve) — the exact failure that
        crashed nba_value/PGP when `gold/marts` pointed at an absent host mount;
      * a symlink (even a valid one) — the canonical layout uses real
        directories only, no alias indirection;
      * a non-directory file;
      * a directory whose resolved path escapes DATA_ROOT.

    A path that simply does not exist yet is allowed (ensure_directories_exist
    will create it). This is a structural contract, not a defensive fallback:
    it never repairs anything, it only refuses to proceed on a broken layout.
    """
    data_root_resolved = DATA_ROOT.resolve()
    problems = []
    for d in MANAGED_DIRECTORIES:
        if d.is_symlink():
            target = os.readlink(d)
            state = "dangling" if not d.exists() else f"symlink -> {target}"
            problems.append(f"{d} is a symlink ({state}); canonical layout forbids aliases")
            continue
        if not d.exists():
            continue  # not created yet -- ensure_directories_exist() will mkdir it
        if not d.is_dir():
            problems.append(f"{d} exists but is not a directory")
            continue
        resolved = d.resolve()
        if data_root_resolved not in resolved.parents and resolved != data_root_resolved:
            problems.append(f"{d} resolves to {resolved}, outside DATA_ROOT {data_root_resolved}")
    if problems:
        raise RuntimeError(
            "Gold layout contract violation (gold/products is the single canonical "
            "product dir; the gold/marts symlink alias was eliminated 2026-06-19):\n  - "
            + "\n  - ".join(problems)
        )


def get_legacy_path(name: str) -> Optional[Path]:
    """Get legacy path (for migration only)."""
    return LEGACY_PATHS.get(name)


def print_path_summary() -> None:
    """Print summary of all configured paths for debugging."""
    print("\n" + "="*70)
    print("DATA PIPELINE PATH SUMMARY")
    print("="*70)

    print(f"\nROOT: {DATA_ROOT}")

    print(f"\n── SILVER FACTS ({SILVER_FACTS_ROOT})")
    for name, path in SILVER_FACTS.items():
        exists = "✓" if path.exists() else "✗"
        print(f"   [{exists}] {name}: {path.name}")

    print(f"\n── SILVER DIMS ({SILVER_DIMS_ROOT})")
    for name, path in SILVER_DIMS.items():
        exists = "✓" if path.exists() else "✗"
        print(f"   [{exists}] {name}: {path.name}")

    print(f"\n── SILVER SUPPLEMENTS ({SILVER_SUPPLEMENTS_ROOT})")
    for name, path in SILVER_SUPPLEMENTS.items():
        exists = "✓" if path.exists() else "✗"
        print(f"   [{exists}] {name}: {path.name}")

    print(f"\n── GOLD FEATURES ({GOLD_FEATURES_ROOT})")
    for name, path in GOLD_FEATURES.items():
        exists = "✓" if path.exists() else "✗"
        print(f"   [{exists}] {name}: {path.name}")

    print(f"\n── GOLD PRODUCTS ({GOLD_PRODUCTS_ROOT})")
    for name, path in GOLD_PRODUCTS.items():
        exists = "✓" if path.exists() else "✗"
        print(f"   [{exists}] {name}: {path.name}")

    print("\n" + "="*70)


if __name__ == "__main__":
    print_path_summary()
