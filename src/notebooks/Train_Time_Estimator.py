# Databricks notebook source
# MAGIC %md
# MAGIC # Train Time Estimator Model
# MAGIC
# MAGIC Trains ML model to predict race times based on training load features.

# COMMAND ----------

import mlflow

from src.feature_engineering.config import FeatureConfig, MLConfig
from src.ml.time_estimator.train import prepare_training_data, train_time_estimator

# COMMAND ----------

feature_config = FeatureConfig()
ml_config = MLConfig()

print(f"Experiment: {ml_config.time_estimator_experiment}")
print(f"Model registry: {ml_config.time_estimator_registry_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prepare Training Data

# COMMAND ----------

training_df = prepare_training_data(spark, config=feature_config)
training_df.cache()

print(f"Training samples: {training_df.count()}")
display(training_df.groupBy("distance_bucket").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Train Model for 10K

# COMMAND ----------

run_id = train_time_estimator(
    training_df,
    target_distance="10k",
    ml_config=ml_config,
    feature_config=feature_config
)

print(f"Run ID: {run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## View Results

# COMMAND ----------

# Get run details
run = mlflow.get_run(run_id)
print("Metrics:")
for key, value in run.data.metrics.items():
    print(f"  {key}: {value:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Train Other Distances (Optional)

# COMMAND ----------

# Uncomment to train all distances
# from src.ml.time_estimator.train import train_all_distances
# results = train_all_distances(spark, ml_config, feature_config)
# print(results)

# COMMAND ----------

training_df.unpersist()
