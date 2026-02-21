"""Feature Engineering module for Athlete Data Platform.

This module provides functionality for:
- Calculating training load metrics (TSS, CTL, ATL, TSB, ACWR)
- Computing HR zone distributions
- Managing Feature Store tables via Databricks APIs
"""

from src.feature_engineering.config import FeatureConfig
from src.feature_engineering.transformations import (
    calculate_tss,
    calculate_ctl_atl,
    calculate_hr_zones,
    calculate_training_monotony,
    calculate_pace_trends,
)
from src.feature_engineering.feature_store_client import AthleteFeatureStore

__all__ = [
    "FeatureConfig",
    "calculate_tss",
    "calculate_ctl_atl",
    "calculate_hr_zones",
    "calculate_training_monotony",
    "calculate_pace_trends",
    "AthleteFeatureStore",
]
