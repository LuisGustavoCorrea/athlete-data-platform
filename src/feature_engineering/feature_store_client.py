"""Feature Store client wrapper for Databricks Feature Engineering.

This module provides a simplified interface for:
- Creating and updating feature tables
- Reading features for training and inference
- Managing feature lookups
"""

from typing import Optional
from pyspark.sql import DataFrame, SparkSession

from src.feature_engineering.config import FeatureConfig
from src.feature_engineering.schemas import FEATURE_TABLE_CONFIGS


class AthleteFeatureStore:
    """Wrapper for Databricks Feature Store operations.

    This class provides methods to create, update, and read feature tables
    using the Databricks Feature Engineering API.

    Example:
        ```python
        fs = AthleteFeatureStore()
        fs.create_or_update_table(
            name="activity_features",
            df=features_df
        )
        ```
    """

    def __init__(
        self,
        catalog: str = None,
        schema: str = None,
        config: FeatureConfig = None
    ):
        """Initialize the Feature Store client.

        Args:
            catalog: Unity Catalog name (default from config)
            schema: Schema name for feature tables (default from config)
            config: FeatureConfig instance
        """
        self.config = config or FeatureConfig()
        self.catalog = catalog or self.config.catalog
        self.schema = schema or self.config.feature_schema

        # Lazy import to avoid issues outside Databricks
        self._fe_client = None

    @property
    def fe(self):
        """Lazy-load Feature Engineering client."""
        if self._fe_client is None:
            try:
                from databricks.feature_engineering import FeatureEngineeringClient
                self._fe_client = FeatureEngineeringClient()
            except ImportError:
                raise ImportError(
                    "databricks-feature-engineering package not found. "
                    "This code must run on Databricks."
                )
        return self._fe_client

    def _get_full_table_name(self, table_name: str) -> str:
        """Get fully qualified table name."""
        if "." in table_name:
            return table_name
        return f"{self.catalog}.{self.schema}.{table_name}"

    def table_exists(self, table_name: str) -> bool:
        """Check if a feature table exists.

        Args:
            table_name: Table name (short or fully qualified)

        Returns:
            True if table exists, False otherwise
        """
        full_name = self._get_full_table_name(table_name)
        try:
            self.fe.get_table(full_name)
            return True
        except Exception:
            return False

    def create_table(
        self,
        name: str,
        df: DataFrame,
        primary_keys: list[str] = None,
        timestamp_keys: list[str] = None,
        description: str = ""
    ) -> None:
        """Create a new feature table.

        Args:
            name: Table name (short name will be prefixed with catalog.schema)
            df: DataFrame with feature data
            primary_keys: List of primary key column names
            timestamp_keys: List of timestamp key column names (for point-in-time)
            description: Table description
        """
        full_name = self._get_full_table_name(name)
        short_name = name.split(".")[-1] if "." in name else name

        # Get config from schema definitions if not provided
        if short_name in FEATURE_TABLE_CONFIGS:
            table_config = FEATURE_TABLE_CONFIGS[short_name]
            primary_keys = primary_keys or table_config["primary_keys"]
            timestamp_keys = timestamp_keys or table_config.get("timestamp_keys")
            description = description or table_config.get("description", "")

        create_kwargs = {
            "name": full_name,
            "primary_keys": primary_keys,
            "df": df,
            "description": description,
        }

        if timestamp_keys:
            create_kwargs["timestamp_keys"] = timestamp_keys

        self.fe.create_table(**create_kwargs)
        print(f"Created feature table: {full_name}")

    def write_table(
        self,
        name: str,
        df: DataFrame,
        mode: str = "merge"
    ) -> None:
        """Write data to an existing feature table.

        Args:
            name: Table name
            df: DataFrame with feature data
            mode: Write mode - "merge" (upsert) or "overwrite"
        """
        full_name = self._get_full_table_name(name)
        self.fe.write_table(
            name=full_name,
            df=df,
            mode=mode
        )
        print(f"Wrote {df.count()} rows to {full_name} (mode={mode})")

    def create_or_update_table(
        self,
        name: str,
        df: DataFrame,
        primary_keys: list[str] = None,
        timestamp_keys: list[str] = None,
        description: str = "",
        mode: str = "merge"
    ) -> None:
        """Create a feature table if it doesn't exist, or update if it does.

        Args:
            name: Table name
            df: DataFrame with feature data
            primary_keys: List of primary key column names
            timestamp_keys: List of timestamp key column names
            description: Table description
            mode: Write mode for updates
        """
        if self.table_exists(name):
            self.write_table(name, df, mode=mode)
        else:
            self.create_table(
                name=name,
                df=df,
                primary_keys=primary_keys,
                timestamp_keys=timestamp_keys,
                description=description
            )

    def read_table(self, name: str) -> DataFrame:
        """Read a feature table as a DataFrame.

        Args:
            name: Table name

        Returns:
            DataFrame with feature data
        """
        full_name = self._get_full_table_name(name)
        spark = SparkSession.builder.getOrCreate()
        return spark.table(full_name)

    def create_training_set(
        self,
        df: DataFrame,
        feature_lookups: list,
        label: str,
        exclude_columns: list[str] = None
    ):
        """Create a training set with automatic feature lookup.

        Args:
            df: DataFrame with entity keys and labels
            feature_lookups: List of FeatureLookup objects
            label: Label column name
            exclude_columns: Columns to exclude from training set

        Returns:
            TrainingSet object
        """
        return self.fe.create_training_set(
            df=df,
            feature_lookups=feature_lookups,
            label=label,
            exclude_columns=exclude_columns or []
        )

    def get_feature_lookups(
        self,
        tables: list[str],
        lookup_keys: dict[str, list[str]],
        feature_names: dict[str, list[str]] = None
    ) -> list:
        """Create FeatureLookup objects for multiple tables.

        Args:
            tables: List of table names
            lookup_keys: Dict mapping table name to lookup key columns
            feature_names: Dict mapping table name to feature columns (None = all)

        Returns:
            List of FeatureLookup objects
        """
        from databricks.feature_engineering import FeatureLookup

        lookups = []
        for table in tables:
            full_name = self._get_full_table_name(table)
            lookup_kwargs = {
                "table_name": full_name,
                "lookup_key": lookup_keys.get(table, []),
            }
            if feature_names and table in feature_names:
                lookup_kwargs["feature_names"] = feature_names[table]

            lookups.append(FeatureLookup(**lookup_kwargs))

        return lookups

    def log_model(
        self,
        model,
        artifact_path: str,
        training_set,
        registered_model_name: str = None
    ):
        """Log a model with feature store integration.

        Args:
            model: Trained model object
            artifact_path: Path in MLflow artifacts
            training_set: TrainingSet used for training
            registered_model_name: Name for model registry (optional)
        """
        import mlflow

        log_kwargs = {
            "model": model,
            "artifact_path": artifact_path,
            "flavor": mlflow.sklearn,
            "training_set": training_set,
        }

        if registered_model_name:
            log_kwargs["registered_model_name"] = registered_model_name

        self.fe.log_model(**log_kwargs)
        print(f"Logged model to {artifact_path}")

    def score_batch(
        self,
        model_uri: str,
        df: DataFrame,
        result_type: str = "double"
    ) -> DataFrame:
        """Score a batch using a logged model with automatic feature lookup.

        Args:
            model_uri: MLflow model URI
            df: DataFrame with entity keys
            result_type: Result column type

        Returns:
            DataFrame with predictions
        """
        return self.fe.score_batch(
            model_uri=model_uri,
            df=df,
            result_type=result_type
        )


def create_feature_schema(spark: SparkSession, config: FeatureConfig = None) -> None:
    """Create the feature_store schema if it doesn't exist.

    Args:
        spark: SparkSession
        config: FeatureConfig instance
    """
    if config is None:
        config = FeatureConfig()

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{config.feature_schema}")
    print(f"Schema {config.catalog}.{config.feature_schema} ready")


def create_gold_schema(spark: SparkSession, config: FeatureConfig = None) -> None:
    """Create the gold schema if it doesn't exist.

    Args:
        spark: SparkSession
        config: FeatureConfig instance
    """
    if config is None:
        config = FeatureConfig()

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{config.gold_schema}")
    print(f"Schema {config.catalog}.{config.gold_schema} ready")
