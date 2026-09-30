# api/src/ml/io/__init__.py
"""
I/O utilities and path management for ML pipeline.

This module provides the canonical paths and utilities for the Bronze-Silver-Gold
data architecture. All trainers and pipelines should import from here.

USAGE:
    from src.ml.io import GOLD_FEATURES, get_gold_feature_path

    # Load player game features
    features_path = GOLD_FEATURES["PLAYER_GAME"]
    df = pd.read_parquet(features_path)

    # Or use helper
    features_path = get_gold_feature_path("player_game")
"""

from .paths import (
    # Root paths
    API_ROOT,
    DATA_ROOT,
    ML_DATA_ROOT,
    SILVER_ROOT,
    GOLD_ROOT,
    # Layer paths
    SILVER_FACTS_ROOT,
    SILVER_DIMS_ROOT,
    SILVER_SUPPLEMENTS_ROOT,
    GOLD_FEATURES_ROOT,
    GOLD_PRODUCTS_ROOT,
    # Path dictionaries
    SILVER_FACTS,
    SILVER_DIMS,
    SILVER_SUPPLEMENTS,
    GOLD_FEATURES,
    GOLD_PRODUCTS,
    LEGACY_PATHS,
    VALIDATION_ARTIFACTS,
    # Registry paths
    REGISTRY_ROOT,
    MANIFESTS_ROOT,
    AUDIT_ROOT,
    # Helper functions
    get_silver_fact_path,
    get_silver_dim_path,
    get_silver_supplement_path,
    get_gold_feature_path,
    get_gold_product_path,
    get_legacy_path,
    ensure_directories_exist,
    validate_gold_layout,
    print_path_summary,
)

__all__ = [
    # Root paths
    "API_ROOT",
    "DATA_ROOT",
    "ML_DATA_ROOT",
    "SILVER_ROOT",
    "GOLD_ROOT",
    # Layer paths
    "SILVER_FACTS_ROOT",
    "SILVER_DIMS_ROOT",
    "SILVER_SUPPLEMENTS_ROOT",
    "GOLD_FEATURES_ROOT",
    "GOLD_PRODUCTS_ROOT",
    # Path dictionaries
    "SILVER_FACTS",
    "SILVER_DIMS",
    "SILVER_SUPPLEMENTS",
    "GOLD_FEATURES",
    "GOLD_PRODUCTS",
    "LEGACY_PATHS",
    "VALIDATION_ARTIFACTS",
    # Registry paths
    "REGISTRY_ROOT",
    "MANIFESTS_ROOT",
    "AUDIT_ROOT",
    # Helper functions
    "get_silver_fact_path",
    "get_silver_dim_path",
    "get_silver_supplement_path",
    "get_gold_feature_path",
    "get_gold_product_path",
    "get_legacy_path",
    "ensure_directories_exist",
    "validate_gold_layout",
    "print_path_summary",
]
