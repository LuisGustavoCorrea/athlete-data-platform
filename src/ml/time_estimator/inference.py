"""Inference script for Time Estimator model."""

from typing import Optional

import mlflow
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.feature_engineering.config import FeatureConfig, MLConfig


def load_model(
    target_distance: str = "10k",
    stage: str = "Production",
    ml_config: MLConfig = None
):
    """Load a registered model from Unity Catalog.

    Args:
        target_distance: Distance bucket (5k, 10k, 21k, 42k)
        stage: Model stage (Production, Staging, None)
        ml_config: MLConfig instance

    Returns:
        Loaded model
    """
    if ml_config is None:
        ml_config = MLConfig()

    model_name = f"{ml_config.time_estimator_registry_name}_{target_distance}"

    if stage:
        model_uri = f"models:/{model_name}/{stage}"
    else:
        model_uri = f"models:/{model_name}/latest"

    return mlflow.sklearn.load_model(model_uri)


def predict_race_times(
    df: DataFrame,
    target_distance: str = "10k",
    model = None,
    ml_config: MLConfig = None
) -> DataFrame:
    """Predict race times for athletes.

    Args:
        df: DataFrame with rolling features (must have feature columns)
        target_distance: Distance to predict
        model: Pre-loaded model (optional, will load if not provided)
        ml_config: MLConfig instance

    Returns:
        DataFrame with predictions added
    """
    import pandas as pd
    from pyspark.sql.types import DoubleType

    if ml_config is None:
        ml_config = MLConfig()

    if model is None:
        model = load_model(target_distance, ml_config=ml_config)

    # Feature columns expected by model
    feature_cols = [
        "ctl_42d", "atl_7d", "tsb", "acwr",
        "pace_trend_30d", "consistency_score",
        "avg_pace_30d", "best_pace_30d", "activities_30d"
    ]

    # Create prediction UDF
    @F.pandas_udf(DoubleType())
    def predict_udf(*cols):
        X = pd.DataFrame({col: data for col, data in zip(feature_cols, cols)})
        X = X.fillna(0)
        return pd.Series(model.predict(X))

    # Add prediction column
    prediction_col = f"predicted_{target_distance}_seconds"
    df = df.withColumn(
        prediction_col,
        predict_udf(*[F.col(c) for c in feature_cols])
    )

    # Also add formatted time
    df = df.withColumn(
        f"predicted_{target_distance}_formatted",
        F.concat(
            (F.col(prediction_col) / 3600).cast("int"),
            F.lit(":"),
            F.lpad(((F.col(prediction_col) % 3600) / 60).cast("int"), 2, "0"),
            F.lit(":"),
            F.lpad((F.col(prediction_col) % 60).cast("int"), 2, "0")
        )
    )

    return df


def batch_inference(
    spark,
    output_table: str = None,
    feature_config: FeatureConfig = None,
    ml_config: MLConfig = None
) -> DataFrame:
    """Run batch inference for all athletes and distances.

    Args:
        spark: SparkSession
        output_table: Table to write results (optional)
        feature_config: FeatureConfig instance
        ml_config: MLConfig instance

    Returns:
        DataFrame with all predictions
    """
    if feature_config is None:
        feature_config = FeatureConfig()

    if ml_config is None:
        ml_config = MLConfig()

    # Read latest rolling features
    rolling_df = spark.table(feature_config.rolling_features_full_name)

    # Get most recent date per athlete
    latest_df = rolling_df.groupBy("athlete_id").agg(
        F.max("as_of_date").alias("as_of_date")
    )

    features_df = rolling_df.join(
        latest_df,
        ["athlete_id", "as_of_date"],
        "inner"
    )

    # Predict for each distance
    result_df = features_df
    for distance in ml_config.time_estimator_targets:
        try:
            model = load_model(distance, stage=None, ml_config=ml_config)
            result_df = predict_race_times(
                result_df,
                target_distance=distance,
                model=model,
                ml_config=ml_config
            )
            print(f"Predictions generated for {distance}")
        except Exception as e:
            print(f"Could not predict for {distance}: {e}")

    # Write to gold table if specified
    if output_table:
        result_df.write.format("delta").mode("overwrite").saveAsTable(output_table)
        print(f"Predictions written to {output_table}")

    return result_df
