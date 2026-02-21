# Databricks notebook source
# MAGIC %md
# MAGIC # Feature Engineering: Activity Features
# MAGIC
# MAGIC Calculates per-activity features from Silver layer data.

# COMMAND ----------

from pyspark.sql import functions as F

from src.feature_engineering.config import FeatureConfig
from src.feature_engineering.transformations import (
    calculate_basic_metrics,
    calculate_tss,
    calculate_hr_zones,
)
from src.feature_engineering.feature_store_client import (
    AthleteFeatureStore,
    create_feature_schema,
)

# COMMAND ----------

# Configuration
config = FeatureConfig()
fs = AthleteFeatureStore(config=config)

# Ensure schema exists
create_feature_schema(spark, config)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Silver Data

# COMMAND ----------

# Read activities
activities_df = spark.table(config.silver_activities_table)

# Read sub-activities for HR data
sub_activity_df = spark.table(config.silver_sub_activity_table)

print(f"Activities: {activities_df.count()}")
print(f"Sub-activities: {sub_activity_df.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Aggregate HR Data from Sub-Activities

# COMMAND ----------

# Aggregate HR data per activity
hr_agg_df = sub_activity_df.groupBy("athlete_id", "activity_id").agg(
    F.avg("average_heartrate").alias("avg_hr"),
    F.max("max_heartrate").alias("max_hr"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Calculate Activity Features

# COMMAND ----------

# Prepare base features
features_df = activities_df.select(
    F.col("athlete_id").cast("string"),
    F.col("id").alias("activity_id"),
    F.col("start_date").alias("event_timestamp"),
    "sport_type",
    "distance_km",
    "moving_time",
    "elapsed_time",
    F.col("pace_min_km"),
    F.col("total_elevation_gain").alias("elevation_gain"),
)

# Calculate basic metrics
features_df = calculate_basic_metrics(features_df)

# Calculate TSS
features_df = calculate_tss(features_df, config=config)

# Join HR data
features_df = features_df.join(
    hr_agg_df,
    ["athlete_id", "activity_id"],
    "left"
)

# Calculate HR zones
features_df = calculate_hr_zones(features_df, config=config)

# Select final columns
features_df = features_df.select(
    "athlete_id",
    "activity_id",
    "event_timestamp",
    "sport_type",
    "distance_km",
    "moving_time_min",
    "elapsed_time_min",
    "pace_min_km",
    F.col("elevation_gain").alias("elevation_gain_m"),
    "elevation_per_km",
    "estimated_tss",
    "intensity_factor",
    "avg_hr",
    "max_hr",
    "hr_zone_1_pct",
    "hr_zone_2_pct",
    "hr_zone_3_pct",
    "hr_zone_4_pct",
    "hr_zone_5_pct",
    "efficiency_index",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Feature Store

# COMMAND ----------

display(features_df.limit(10))

# COMMAND ----------

# Write to Feature Store
fs.create_or_update_table(
    name="activity_features",
    df=features_df,
)

print(f"Activity features written: {features_df.count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation

# COMMAND ----------

# Verify data
validation_df = fs.read_table("activity_features")
print(f"Total rows in table: {validation_df.count()}")
print(f"Distinct athletes: {validation_df.select('athlete_id').distinct().count()}")
