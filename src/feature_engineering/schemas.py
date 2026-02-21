"""Schema definitions for Feature Store tables."""

from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    DoubleType,
    TimestampType,
    DateType,
    IntegerType,
    BooleanType,
)


# Activity Features Schema
ACTIVITY_FEATURES_SCHEMA = StructType([
    # Primary keys
    StructField("athlete_id", StringType(), nullable=False),
    StructField("activity_id", LongType(), nullable=False),
    StructField("event_timestamp", TimestampType(), nullable=False),

    # Basic metrics
    StructField("sport_type", StringType(), nullable=True),
    StructField("distance_km", DoubleType(), nullable=True),
    StructField("moving_time_min", DoubleType(), nullable=True),
    StructField("elapsed_time_min", DoubleType(), nullable=True),
    StructField("pace_min_km", DoubleType(), nullable=True),
    StructField("elevation_gain_m", DoubleType(), nullable=True),
    StructField("elevation_per_km", DoubleType(), nullable=True),

    # Training load
    StructField("estimated_tss", DoubleType(), nullable=True),
    StructField("intensity_factor", DoubleType(), nullable=True),

    # HR metrics (nullable - not all activities have HR)
    StructField("avg_hr", DoubleType(), nullable=True),
    StructField("max_hr", DoubleType(), nullable=True),
    StructField("hr_zone_1_pct", DoubleType(), nullable=True),
    StructField("hr_zone_2_pct", DoubleType(), nullable=True),
    StructField("hr_zone_3_pct", DoubleType(), nullable=True),
    StructField("hr_zone_4_pct", DoubleType(), nullable=True),
    StructField("hr_zone_5_pct", DoubleType(), nullable=True),
    StructField("efficiency_index", DoubleType(), nullable=True),
])

ACTIVITY_FEATURES_PRIMARY_KEYS = ["athlete_id", "activity_id"]
ACTIVITY_FEATURES_TIMESTAMP_KEYS = ["event_timestamp"]


# Daily Features Schema
DAILY_FEATURES_SCHEMA = StructType([
    # Primary keys
    StructField("athlete_id", StringType(), nullable=False),
    StructField("activity_date", DateType(), nullable=False),

    # Daily aggregates
    StructField("daily_activities", IntegerType(), nullable=True),
    StructField("daily_distance_km", DoubleType(), nullable=True),
    StructField("daily_tss", DoubleType(), nullable=True),
    StructField("daily_elevation_m", DoubleType(), nullable=True),
    StructField("daily_moving_time_min", DoubleType(), nullable=True),
    StructField("avg_pace_day", DoubleType(), nullable=True),
    StructField("best_pace_day", DoubleType(), nullable=True),
    StructField("is_rest_day", BooleanType(), nullable=True),
])

DAILY_FEATURES_PRIMARY_KEYS = ["athlete_id", "activity_date"]
DAILY_FEATURES_TIMESTAMP_KEYS = ["activity_date"]


# Weekly Features Schema
WEEKLY_FEATURES_SCHEMA = StructType([
    # Primary keys
    StructField("athlete_id", StringType(), nullable=False),
    StructField("week_start", DateType(), nullable=False),  # Monday

    # Weekly aggregates
    StructField("weekly_activities", IntegerType(), nullable=True),
    StructField("weekly_distance_km", DoubleType(), nullable=True),
    StructField("weekly_tss", DoubleType(), nullable=True),
    StructField("weekly_elevation_m", DoubleType(), nullable=True),
    StructField("weekly_moving_time_min", DoubleType(), nullable=True),
    StructField("avg_pace_week", DoubleType(), nullable=True),
    StructField("best_pace_week", DoubleType(), nullable=True),

    # Training load metrics
    StructField("training_monotony", DoubleType(), nullable=True),
    StructField("training_strain", DoubleType(), nullable=True),
    StructField("training_days", IntegerType(), nullable=True),
    StructField("rest_days", IntegerType(), nullable=True),
])

WEEKLY_FEATURES_PRIMARY_KEYS = ["athlete_id", "week_start"]
WEEKLY_FEATURES_TIMESTAMP_KEYS = ["week_start"]


# Rolling Features Schema
ROLLING_FEATURES_SCHEMA = StructType([
    # Primary keys
    StructField("athlete_id", StringType(), nullable=False),
    StructField("as_of_date", DateType(), nullable=False),

    # Training load (exponential moving averages)
    StructField("ctl_42d", DoubleType(), nullable=True),  # Chronic Training Load (Fitness)
    StructField("atl_7d", DoubleType(), nullable=True),   # Acute Training Load (Fatigue)
    StructField("tsb", DoubleType(), nullable=True),      # Training Stress Balance (Form)
    StructField("acwr", DoubleType(), nullable=True),     # Acute:Chronic Workload Ratio

    # Trends
    StructField("pace_trend_30d", DoubleType(), nullable=True),     # Negative = improving
    StructField("distance_trend_30d", DoubleType(), nullable=True),  # Positive = increasing volume
    StructField("consistency_score", DoubleType(), nullable=True),   # % of expected training days

    # Rolling aggregates
    StructField("activities_7d", IntegerType(), nullable=True),
    StructField("activities_30d", IntegerType(), nullable=True),
    StructField("total_distance_7d_km", DoubleType(), nullable=True),
    StructField("total_distance_30d_km", DoubleType(), nullable=True),
    StructField("avg_pace_30d", DoubleType(), nullable=True),
    StructField("best_pace_30d", DoubleType(), nullable=True),

    # Risk indicators
    StructField("training_monotony_7d", DoubleType(), nullable=True),
    StructField("training_strain_7d", DoubleType(), nullable=True),
    StructField("rest_days_14d", IntegerType(), nullable=True),
    StructField("is_overtraining_risk", BooleanType(), nullable=True),
])

ROLLING_FEATURES_PRIMARY_KEYS = ["athlete_id", "as_of_date"]
ROLLING_FEATURES_TIMESTAMP_KEYS = ["as_of_date"]


# Feature table configurations for Feature Store API
FEATURE_TABLE_CONFIGS = {
    "activity_features": {
        "primary_keys": ACTIVITY_FEATURES_PRIMARY_KEYS,
        "timestamp_keys": ACTIVITY_FEATURES_TIMESTAMP_KEYS,
        "schema": ACTIVITY_FEATURES_SCHEMA,
        "description": "Per-activity features including pace, elevation, TSS, and HR zones",
    },
    "athlete_daily_features": {
        "primary_keys": DAILY_FEATURES_PRIMARY_KEYS,
        "timestamp_keys": DAILY_FEATURES_TIMESTAMP_KEYS,
        "schema": DAILY_FEATURES_SCHEMA,
        "description": "Daily aggregated features per athlete",
    },
    "athlete_weekly_features": {
        "primary_keys": WEEKLY_FEATURES_PRIMARY_KEYS,
        "timestamp_keys": WEEKLY_FEATURES_TIMESTAMP_KEYS,
        "schema": WEEKLY_FEATURES_SCHEMA,
        "description": "Weekly aggregated features including monotony and strain",
    },
    "athlete_rolling_features": {
        "primary_keys": ROLLING_FEATURES_PRIMARY_KEYS,
        "timestamp_keys": ROLLING_FEATURES_TIMESTAMP_KEYS,
        "schema": ROLLING_FEATURES_SCHEMA,
        "description": "Rolling window features for training load (CTL/ATL/TSB) and trends",
    },
}
