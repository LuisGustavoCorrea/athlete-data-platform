# Databricks notebook source
# MAGIC %md
# MAGIC # Batch Inference
# MAGIC
# MAGIC Generates predictions for all athletes and writes to Gold layer.

# COMMAND ----------

from pyspark.sql import functions as F

from src.feature_engineering.config import FeatureConfig, MLConfig
from src.feature_engineering.feature_store_client import create_gold_schema
from src.ml.time_estimator.inference import batch_inference

# COMMAND ----------

feature_config = FeatureConfig()
ml_config = MLConfig()

# Ensure gold schema exists
create_gold_schema(spark, feature_config)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Batch Inference

# COMMAND ----------

output_table = f"{feature_config.catalog}.{feature_config.gold_schema}.athlete_predictions"

predictions_df = batch_inference(
    spark,
    output_table=output_table,
    feature_config=feature_config,
    ml_config=ml_config
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## View Predictions

# COMMAND ----------

display(predictions_df.select(
    "athlete_id",
    "as_of_date",
    "ctl_42d",
    "atl_7d",
    "tsb",
    "predicted_10k_formatted",
    "is_overtraining_risk"
))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation

# COMMAND ----------

result_df = spark.table(output_table)
print(f"Predictions in gold table: {result_df.count()}")
