"""Training script for Time Estimator model.

This model predicts race finish times based on training load and pace trends.
"""

from typing import Optional
import numpy as np

from pyspark.sql import DataFrame

from src.feature_engineering.config import FeatureConfig, MLConfig


def prepare_training_data(
    spark,
    config: FeatureConfig = None,
    min_activities: int = 10
) -> DataFrame:
    """Prepare training data from feature tables.

    Joins rolling features with actual race results to create training set.

    Args:
        spark: SparkSession
        config: FeatureConfig instance
        min_activities: Minimum activities required for an athlete

    Returns:
        DataFrame with features and target
    """
    if config is None:
        config = FeatureConfig()

    # Read rolling features
    rolling_df = spark.table(config.rolling_features_full_name)

    # Read activity data for actual race times
    activities_df = spark.table(config.silver_activities_table)

    # Filter to activities that could be "race-like" (fast pace, consistent)
    # For MVP, we'll use the best times as targets
    from pyspark.sql import functions as F

    # Get best times per distance bucket
    activities_df = activities_df.withColumn(
        "distance_bucket",
        F.when(F.col("distance_km").between(4.5, 5.5), "5k")
        .when(F.col("distance_km").between(9.5, 10.5), "10k")
        .when(F.col("distance_km").between(20, 22), "21k")
        .when(F.col("distance_km").between(41, 43), "42k")
        .otherwise(None)
    ).filter(F.col("distance_bucket").isNotNull())

    # Get moving time in seconds as target
    activities_df = activities_df.withColumn(
        "race_time_seconds",
        F.col("moving_time")
    ).withColumn(
        "activity_date",
        F.to_date("start_date")
    )

    # Join with rolling features (as of race date)
    training_df = activities_df.join(
        rolling_df,
        (activities_df.athlete_id == rolling_df.athlete_id) &
        (activities_df.activity_date == rolling_df.as_of_date),
        "inner"
    ).select(
        activities_df.athlete_id,
        activities_df.activity_date,
        "distance_bucket",
        "race_time_seconds",
        "ctl_42d",
        "atl_7d",
        "tsb",
        "acwr",
        "pace_trend_30d",
        "consistency_score",
        "avg_pace_30d",
        "best_pace_30d",
        "activities_30d",
    )

    return training_df


def train_time_estimator(
    training_df: DataFrame,
    target_distance: str = "10k",
    ml_config: MLConfig = None,
    feature_config: FeatureConfig = None
) -> str:
    """Train time estimator model with MLflow tracking.

    Args:
        training_df: DataFrame with features and target
        target_distance: Distance bucket to train for (5k, 10k, 21k, 42k)
        ml_config: MLConfig instance
        feature_config: FeatureConfig instance

    Returns:
        MLflow run ID
    """
    import mlflow
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    if ml_config is None:
        ml_config = MLConfig()

    if feature_config is None:
        feature_config = FeatureConfig()

    # Set experiment
    mlflow.set_experiment(ml_config.time_estimator_experiment)

    # Filter to target distance
    from pyspark.sql import functions as F
    filtered_df = training_df.filter(F.col("distance_bucket") == target_distance)

    # Convert to pandas
    pdf = filtered_df.toPandas()

    if len(pdf) < 10:
        raise ValueError(f"Not enough data for {target_distance}: {len(pdf)} rows")

    # Feature columns
    feature_cols = [
        "ctl_42d", "atl_7d", "tsb", "acwr",
        "pace_trend_30d", "consistency_score",
        "avg_pace_30d", "best_pace_30d", "activities_30d"
    ]

    # Prepare X and y
    X = pdf[feature_cols].fillna(0)
    y = pdf["race_time_seconds"]

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=ml_config.test_size,
        random_state=ml_config.random_state
    )

    with mlflow.start_run(run_name=f"time_estimator_{target_distance}") as run:
        # Log parameters
        mlflow.log_param("target_distance", target_distance)
        mlflow.log_param("n_estimators", ml_config.n_estimators)
        mlflow.log_param("max_depth", ml_config.max_depth)
        mlflow.log_param("learning_rate", ml_config.learning_rate)
        mlflow.log_param("training_samples", len(X_train))
        mlflow.log_param("test_samples", len(X_test))
        mlflow.log_param("feature_cols", feature_cols)

        # Train model
        model = GradientBoostingRegressor(
            n_estimators=ml_config.n_estimators,
            max_depth=ml_config.max_depth,
            learning_rate=ml_config.learning_rate,
            random_state=ml_config.random_state
        )
        model.fit(X_train, y_train)

        # Evaluate
        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        rmse = np.sqrt(mean_squared_error(y_test, predictions))
        mape = np.mean(np.abs((y_test - predictions) / y_test)) * 100

        # Log metrics
        mlflow.log_metric("mae_seconds", mae)
        mlflow.log_metric("mae_minutes", mae / 60)
        mlflow.log_metric("rmse_seconds", rmse)
        mlflow.log_metric("mape_percent", mape)

        # Log feature importance
        for i, col in enumerate(feature_cols):
            mlflow.log_metric(f"importance_{col}", model.feature_importances_[i])

        # Log model
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name=f"{ml_config.time_estimator_registry_name}_{target_distance}"
        )

        print(f"Model trained for {target_distance}")
        print(f"  MAE: {mae/60:.2f} minutes")
        print(f"  RMSE: {rmse/60:.2f} minutes")
        print(f"  MAPE: {mape:.1f}%")

        return run.info.run_id


def train_all_distances(
    spark,
    ml_config: MLConfig = None,
    feature_config: FeatureConfig = None
) -> dict[str, str]:
    """Train models for all target distances.

    Args:
        spark: SparkSession
        ml_config: MLConfig instance
        feature_config: FeatureConfig instance

    Returns:
        Dict mapping distance to run_id
    """
    if ml_config is None:
        ml_config = MLConfig()

    training_df = prepare_training_data(spark, feature_config)
    training_df.cache()

    results = {}
    for distance in ml_config.time_estimator_targets:
        try:
            run_id = train_time_estimator(
                training_df,
                target_distance=distance,
                ml_config=ml_config,
                feature_config=feature_config
            )
            results[distance] = run_id
        except ValueError as e:
            print(f"Skipping {distance}: {e}")
            results[distance] = None

    training_df.unpersist()
    return results
