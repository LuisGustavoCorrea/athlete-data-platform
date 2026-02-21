"""Feature transformation functions for athlete data.

This module contains PySpark transformation functions for calculating:
- Training Stress Score (TSS)
- Chronic/Acute Training Load (CTL/ATL)
- Training Stress Balance (TSB)
- Acute:Chronic Workload Ratio (ACWR)
- HR zone distributions
- Training monotony and strain
- Pace trends
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.feature_engineering.config import FeatureConfig


def calculate_basic_metrics(df: DataFrame) -> DataFrame:
    """Calculate basic derived metrics from raw activity data.

    Args:
        df: DataFrame with columns: distance_km, moving_time, elapsed_time, elevation_gain

    Returns:
        DataFrame with additional columns: moving_time_min, elapsed_time_min, elevation_per_km
    """
    return df.withColumn(
        "moving_time_min",
        F.col("moving_time") / 60
    ).withColumn(
        "elapsed_time_min",
        F.col("elapsed_time") / 60
    ).withColumn(
        "elevation_per_km",
        F.when(
            F.col("distance_km") > 0,
            F.col("elevation_gain") / F.col("distance_km")
        ).otherwise(0)
    )


def calculate_tss(
    df: DataFrame,
    pace_col: str = "pace_min_km",
    duration_col: str = "moving_time_min",
    threshold_pace: float = None,
    config: FeatureConfig = None
) -> DataFrame:
    """Calculate Training Stress Score (TSS) for running activities.

    TSS estimates the training load based on duration and intensity.
    Formula: TSS = (duration × IF²) / 60 × 100

    Args:
        df: DataFrame with pace and duration columns
        pace_col: Column name for pace (min/km)
        duration_col: Column name for duration (minutes)
        threshold_pace: Threshold pace for IF calculation (default from config)
        config: FeatureConfig instance

    Returns:
        DataFrame with columns: intensity_factor, estimated_tss
    """
    if config is None:
        config = FeatureConfig()

    if threshold_pace is None:
        threshold_pace = config.default_threshold_pace

    # Intensity Factor = threshold_pace / actual_pace
    # Lower pace (faster) = higher IF
    df = df.withColumn(
        "intensity_factor",
        F.when(
            F.col(pace_col) > 0,
            F.lit(threshold_pace) / F.col(pace_col)
        ).otherwise(F.lit(0))
    )

    # TSS = (duration_min × IF²) / 60 × 100
    df = df.withColumn(
        "estimated_tss",
        (F.col(duration_col) * F.pow(F.col("intensity_factor"), 2)) / 60 * 100
    )

    return df


def calculate_hr_zones(
    df: DataFrame,
    hr_col: str = "average_heartrate",
    max_hr_col: str = "max_heartrate",
    config: FeatureConfig = None
) -> DataFrame:
    """Calculate HR zone distribution for activities.

    Zones are based on percentage of max HR:
    - Zone 1: 50-60% (Recovery)
    - Zone 2: 60-70% (Aerobic)
    - Zone 3: 70-80% (Tempo)
    - Zone 4: 80-90% (Threshold)
    - Zone 5: 90-100% (VO2max)

    Args:
        df: DataFrame with HR columns
        hr_col: Column name for average heart rate
        max_hr_col: Column name for max heart rate
        config: FeatureConfig instance

    Returns:
        DataFrame with columns: hr_zone_1_pct through hr_zone_5_pct
    """
    if config is None:
        config = FeatureConfig()

    # Calculate HR percentage of max
    df = df.withColumn(
        "_hr_pct",
        F.when(
            (F.col(max_hr_col).isNotNull()) & (F.col(max_hr_col) > 0),
            F.col(hr_col) / F.col(max_hr_col)
        ).otherwise(F.lit(None))
    )

    # Assign zone based on HR percentage
    for zone_name, (lower, upper) in config.hr_zones.items():
        zone_col = f"hr_{zone_name}_pct"
        df = df.withColumn(
            zone_col,
            F.when(
                (F.col("_hr_pct") >= lower) & (F.col("_hr_pct") < upper),
                F.lit(1.0)
            ).otherwise(F.lit(0.0))
        )

    # Calculate efficiency index (pace per HR unit)
    df = df.withColumn(
        "efficiency_index",
        F.when(
            (F.col(hr_col).isNotNull()) & (F.col(hr_col) > 0),
            F.col("pace_min_km") / F.col(hr_col)
        ).otherwise(F.lit(None))
    )

    # Drop temporary column
    df = df.drop("_hr_pct")

    return df


def aggregate_daily_features(df: DataFrame, athlete_col: str = "athlete_id") -> DataFrame:
    """Aggregate activity features to daily level.

    Args:
        df: DataFrame with activity-level features
        athlete_col: Column name for athlete identifier

    Returns:
        DataFrame with daily aggregated features
    """
    return df.groupBy(athlete_col, F.to_date("start_date").alias("activity_date")).agg(
        F.count("*").alias("daily_activities"),
        F.sum("distance_km").alias("daily_distance_km"),
        F.sum("estimated_tss").alias("daily_tss"),
        F.sum("elevation_gain").alias("daily_elevation_m"),
        F.sum("moving_time_min").alias("daily_moving_time_min"),
        F.avg("pace_min_km").alias("avg_pace_day"),
        F.min("pace_min_km").alias("best_pace_day"),
    ).withColumn(
        "is_rest_day",
        F.lit(False)
    )


def calculate_ctl_atl(
    df: DataFrame,
    athlete_col: str = "athlete_id",
    date_col: str = "activity_date",
    tss_col: str = "daily_tss",
    config: FeatureConfig = None
) -> DataFrame:
    """Calculate Chronic and Acute Training Load using rolling averages.

    CTL (Chronic Training Load): 42-day average - represents "fitness"
    ATL (Acute Training Load): 7-day average - represents "fatigue"
    TSB (Training Stress Balance): CTL - ATL - represents "form"
    ACWR (Acute:Chronic Workload Ratio): ATL / CTL - injury risk indicator

    Args:
        df: DataFrame with daily TSS values
        athlete_col: Column name for athlete identifier
        date_col: Column name for date
        tss_col: Column name for daily TSS
        config: FeatureConfig instance

    Returns:
        DataFrame with columns: ctl_42d, atl_7d, tsb, acwr
    """
    if config is None:
        config = FeatureConfig()

    # Window specifications
    window_42d = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-41 * 86400, 0)  # 42 days in seconds
    )

    window_7d = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-6 * 86400, 0)  # 7 days in seconds
    )

    # Fill nulls with 0 for TSS (rest days = 0 TSS)
    df = df.withColumn(
        "_tss_filled",
        F.coalesce(F.col(tss_col), F.lit(0))
    )

    # CTL (42-day average)
    df = df.withColumn(
        "ctl_42d",
        F.avg("_tss_filled").over(window_42d)
    )

    # ATL (7-day average)
    df = df.withColumn(
        "atl_7d",
        F.avg("_tss_filled").over(window_7d)
    )

    # TSB (Form) = CTL - ATL
    df = df.withColumn(
        "tsb",
        F.col("ctl_42d") - F.col("atl_7d")
    )

    # ACWR (Acute:Chronic Workload Ratio)
    df = df.withColumn(
        "acwr",
        F.when(
            F.col("ctl_42d") > 0,
            F.col("atl_7d") / F.col("ctl_42d")
        ).otherwise(F.lit(0))
    )

    # Drop temporary column
    df = df.drop("_tss_filled")

    return df


def calculate_training_monotony(
    df: DataFrame,
    athlete_col: str = "athlete_id",
    date_col: str = "activity_date",
    tss_col: str = "daily_tss"
) -> DataFrame:
    """Calculate training monotony and strain.

    Monotony = mean(daily_tss) / stddev(daily_tss) over 7 days
    Strain = sum(daily_tss) × monotony

    High monotony (>2.0) indicates repetitive training that increases injury risk.

    Args:
        df: DataFrame with daily TSS values
        athlete_col: Column name for athlete identifier
        date_col: Column name for date
        tss_col: Column name for daily TSS

    Returns:
        DataFrame with columns: training_monotony_7d, training_strain_7d
    """
    window_7d = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-6 * 86400, 0)
    )

    # Calculate monotony = mean / stddev
    df = df.withColumn(
        "_tss_mean_7d",
        F.avg(F.coalesce(F.col(tss_col), F.lit(0))).over(window_7d)
    ).withColumn(
        "_tss_std_7d",
        F.stddev(F.coalesce(F.col(tss_col), F.lit(0))).over(window_7d)
    )

    df = df.withColumn(
        "training_monotony_7d",
        F.when(
            F.col("_tss_std_7d") > 0,
            F.col("_tss_mean_7d") / F.col("_tss_std_7d")
        ).otherwise(F.lit(0))
    )

    # Calculate strain = sum × monotony
    df = df.withColumn(
        "_tss_sum_7d",
        F.sum(F.coalesce(F.col(tss_col), F.lit(0))).over(window_7d)
    ).withColumn(
        "training_strain_7d",
        F.col("_tss_sum_7d") * F.col("training_monotony_7d")
    )

    # Drop temporary columns
    df = df.drop("_tss_mean_7d", "_tss_std_7d", "_tss_sum_7d")

    return df


def calculate_pace_trends(
    df: DataFrame,
    athlete_col: str = "athlete_id",
    date_col: str = "activity_date",
    pace_col: str = "avg_pace_day"
) -> DataFrame:
    """Calculate pace trends over 30 days.

    Negative trend = improving (getting faster)
    Positive trend = declining (getting slower)

    Args:
        df: DataFrame with daily pace values
        athlete_col: Column name for athlete identifier
        date_col: Column name for date
        pace_col: Column name for pace

    Returns:
        DataFrame with column: pace_trend_30d
    """
    window_30d = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    window_first_last = (
        Window.partitionBy(athlete_col)
        .orderBy(date_col)
        .rowsBetween(-29, 0)
    )

    # Simple trend: current vs 30 days ago
    df = df.withColumn(
        "_pace_30d_ago",
        F.first(pace_col).over(window_first_last)
    ).withColumn(
        "_pace_current",
        F.last(pace_col).over(window_first_last)
    )

    df = df.withColumn(
        "pace_trend_30d",
        F.when(
            F.col("_pace_30d_ago").isNotNull() & F.col("_pace_30d_ago") > 0,
            (F.col("_pace_current") - F.col("_pace_30d_ago")) / F.col("_pace_30d_ago")
        ).otherwise(F.lit(0))
    )

    # Distance trend
    window_distance = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    df = df.withColumn(
        "total_distance_30d_km",
        F.sum("daily_distance_km").over(window_distance)
    )

    # Activities count
    df = df.withColumn(
        "activities_30d",
        F.count("*").over(window_distance)
    ).withColumn(
        "activities_7d",
        F.count("*").over(
            Window.partitionBy(athlete_col)
            .orderBy(F.col(date_col).cast("long"))
            .rangeBetween(-6 * 86400, 0)
        )
    )

    # Best pace 30d
    df = df.withColumn(
        "best_pace_30d",
        F.min(pace_col).over(window_30d)
    ).withColumn(
        "avg_pace_30d",
        F.avg(pace_col).over(window_30d)
    )

    # Drop temporary columns
    df = df.drop("_pace_30d_ago", "_pace_current")

    return df


def calculate_consistency_score(
    df: DataFrame,
    athlete_col: str = "athlete_id",
    date_col: str = "activity_date",
    expected_days_per_week: int = 4
) -> DataFrame:
    """Calculate training consistency score.

    Consistency = actual training days / expected training days over 30 days.

    Args:
        df: DataFrame with daily features
        athlete_col: Column name for athlete identifier
        date_col: Column name for date
        expected_days_per_week: Expected training days per week

    Returns:
        DataFrame with column: consistency_score
    """
    window_30d = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-29 * 86400, 0)
    )

    expected_days_30d = (30 / 7) * expected_days_per_week

    df = df.withColumn(
        "_training_days_30d",
        F.count(F.when(F.col("daily_tss") > 0, 1)).over(window_30d)
    ).withColumn(
        "consistency_score",
        F.col("_training_days_30d") / F.lit(expected_days_30d)
    )

    # Rest days in last 14 days
    window_14d = (
        Window.partitionBy(athlete_col)
        .orderBy(F.col(date_col).cast("long"))
        .rangeBetween(-13 * 86400, 0)
    )

    df = df.withColumn(
        "rest_days_14d",
        F.lit(14) - F.count(F.when(F.col("daily_tss") > 0, 1)).over(window_14d)
    )

    df = df.drop("_training_days_30d")

    return df


def calculate_overtraining_risk(
    df: DataFrame,
    config: FeatureConfig = None
) -> DataFrame:
    """Flag activities with overtraining risk.

    Risk indicators:
    - ACWR > 1.5 (high acute:chronic ratio)
    - Training monotony > 2.0
    - TSB < -20 (high accumulated fatigue)

    Args:
        df: DataFrame with training load features
        config: FeatureConfig instance

    Returns:
        DataFrame with column: is_overtraining_risk
    """
    if config is None:
        config = FeatureConfig()

    df = df.withColumn(
        "is_overtraining_risk",
        (F.col("acwr") > config.acwr_risk_threshold) |
        (F.col("training_monotony_7d") > config.monotony_risk_threshold) |
        (F.col("tsb") < -20)
    )

    return df
