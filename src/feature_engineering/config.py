"""Configuration for feature engineering pipeline."""

from dataclasses import dataclass, field


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""

    # Unity Catalog
    catalog: str = "uc_athlete_data"
    feature_schema: str = "feature_store"
    silver_schema: str = "silver"
    gold_schema: str = "gold"

    # HR Zones (% of max HR)
    hr_zones: dict = field(default_factory=lambda: {
        "zone_1": (0.50, 0.60),  # Recovery
        "zone_2": (0.60, 0.70),  # Aerobic
        "zone_3": (0.70, 0.80),  # Tempo
        "zone_4": (0.80, 0.90),  # Threshold
        "zone_5": (0.90, 1.00),  # VO2max
    })

    # Training load parameters
    default_threshold_pace: float = 5.5  # min/km (adjust based on athlete)
    ctl_window_days: int = 42  # Chronic Training Load window
    atl_window_days: int = 7   # Acute Training Load window

    # Risk thresholds
    acwr_risk_threshold: float = 1.5  # Above this = overtraining risk
    acwr_safe_lower: float = 0.8      # Below this = undertrained
    acwr_safe_upper: float = 1.3      # Optimal range upper
    monotony_risk_threshold: float = 2.0

    # Feature table names
    activity_features_table: str = "activity_features"
    daily_features_table: str = "athlete_daily_features"
    weekly_features_table: str = "athlete_weekly_features"
    rolling_features_table: str = "athlete_rolling_features"

    @property
    def activity_features_full_name(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.activity_features_table}"

    @property
    def daily_features_full_name(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.daily_features_table}"

    @property
    def weekly_features_full_name(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.weekly_features_table}"

    @property
    def rolling_features_full_name(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.rolling_features_table}"

    @property
    def silver_activities_table(self) -> str:
        return f"{self.catalog}.{self.silver_schema}.strava_activities"

    @property
    def silver_sub_activity_table(self) -> str:
        return f"{self.catalog}.{self.silver_schema}.strava_sub_activity"


@dataclass
class MLConfig:
    """Configuration for ML training and inference."""

    experiment_base_path: str = "/Shared/athlete-platform"
    model_registry_prefix: str = "uc_athlete_data.models"

    # Time estimator
    time_estimator_targets: list = field(default_factory=lambda: ["5k", "10k", "21k", "42k"])
    time_estimator_model_name: str = "time_estimator"

    # Overtraining detector
    overtraining_model_name: str = "overtraining_detector"

    # Training parameters
    test_size: float = 0.2
    random_state: int = 42

    # Model hyperparameters (XGBoost defaults)
    n_estimators: int = 100
    max_depth: int = 5
    learning_rate: float = 0.1

    @property
    def time_estimator_experiment(self) -> str:
        return f"{self.experiment_base_path}/time-estimator"

    @property
    def overtraining_experiment(self) -> str:
        return f"{self.experiment_base_path}/overtraining-detector"

    @property
    def time_estimator_registry_name(self) -> str:
        return f"{self.model_registry_prefix}.{self.time_estimator_model_name}"

    @property
    def overtraining_registry_name(self) -> str:
        return f"{self.model_registry_prefix}.{self.overtraining_model_name}"
