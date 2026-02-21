# Databricks notebook source
# MAGIC %md
# MAGIC # Feature Engineering: Rolling Features
# MAGIC
# MAGIC Calculates rolling window features: CTL, ATL, TSB, ACWR, trends.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.feature_engineering.config import FeatureConfig
from src.feature_engineering.transformations import (
    calculate_ctl_atl,
    calculate_training_monotony,
    calculate_pace_trends,
    calculate_consistency_score,
    calculate_overtraining_risk,
)
from src.feature_engineering.feature_store_client import AthleteFeatureStore

# COMMAND ----------

config = FeatureConfig()
fs = AthleteFeatureStore(config=config)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Activity Features

# COMMAND ----------

activity_df = fs.read_table("activity_features")
print(f"Activity features: {activity_df.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Aggregate to Daily Level

# COMMAND ----------

# First aggregate to daily
daily_df = activity_df.groupBy(
    "athlete_id",
    F.to_date("event_timestamp").alias("activity_date")
).agg(
    F.count("*").alias("daily_activities"),
    F.sum("distance_km").alias("daily_distance_km"),
    F.sum("estimated_tss").alias("daily_tss"),
    F.sum("elevation_gain_m").alias("daily_elevation_m"),
    F.sum("moving_time_min").alias("daily_moving_time_min"),
    F.avg("pace_min_km").alias("avg_pace_day"),
    F.min("pace_min_km").alias("best_pace_day"),
)

print(f"Daily records: {daily_df.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Date Spine (Fill Missing Days)

# COMMAND ----------

# Get date range per athlete
date_range = daily_df.groupBy("athlete_id").agg(
    F.min("activity_date").alias("min_date"),
    F.max("activity_date").alias("max_date"),
)

# Generate all dates between min and max
def generate_date_spine(spark_session, date_range_df):
    """Generate all dates for each athlete."""
    dates = date_range_df.select(
        "athlete_id",
        F.explode(
            F.sequence(
                F.col("min_date"),
                F.col("max_date"),
                F.expr("INTERVAL 1 DAY")
            )
        ).alias("as_of_date")
    )
    return dates

date_spine = generate_date_spine(spark, date_range)

# Left join to include rest days
full_df = date_spine.join(
    daily_df,
    (date_spine.athlete_id == daily_df.athlete_id) &
    (date_spine.as_of_date == daily_df.activity_date),
    "left"
).select(
    date_spine.athlete_id,
    date_spine.as_of_date.alias("activity_date"),
    F.coalesce(daily_df.daily_tss, F.lit(0)).alias("daily_tss"),
    F.coalesce(daily_df.daily_distance_km, F.lit(0)).alias("daily_distance_km"),
    F.coalesce(daily_df.avg_pace_day, F.lit(None)).alias("avg_pace_day"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Calculate Rolling Features

# COMMAND ----------

# CTL, ATL, TSB, ACWR
rolling_df = calculate_ctl_atl(full_df, config=config)

# Training monotony and strain
rolling_df = calculate_training_monotony(rolling_df)

# Pace trends
rolling_df = calculate_pace_trends(rolling_df)

# Consistency score
rolling_df = calculate_consistency_score(rolling_df)

# Overtraining risk flag
rolling_df = calculate_overtraining_risk(rolling_df, config=config)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prepare Final Schema

# COMMAND ----------

# Rename and select final columns
final_df = rolling_df.select(
    "athlete_id",
    F.col("activity_date").alias("as_of_date"),
    "ctl_42d",
    "atl_7d",
    "tsb",
    "acwr",
    "pace_trend_30d",
    F.lit(None).cast("double").alias("distance_trend_30d"),
    "consistency_score",
    "activities_7d",
    "activities_30d",
    F.col("daily_distance_km").alias("total_distance_7d_km"),
    "total_distance_30d_km",
    "avg_pace_30d",
    "best_pace_30d",
    "training_monotony_7d",
    "training_strain_7d",
    "rest_days_14d",
    "is_overtraining_risk",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Feature Store

# COMMAND ----------

display(final_df.orderBy("athlete_id", "as_of_date").limit(20))

# COMMAND ----------

fs.create_or_update_table(
    name="athlete_rolling_features",
    df=final_df,
)

print(f"Rolling features written: {final_df.count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation

# COMMAND ----------

validation_df = fs.read_table("athlete_rolling_features")
print(f"Total rows: {validation_df.count()}")

# Check for overtraining risk
risk_count = validation_df.filter(F.col("is_overtraining_risk") == True).count()
print(f"Days with overtraining risk: {risk_count}")
