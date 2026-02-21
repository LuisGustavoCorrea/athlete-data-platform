# DESIGN: Feature Store + MLOps para Athlete Platform

> Technical design for implementing Feature Store with MLOps pipeline on Databricks

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | FEATURE_STORE_MLOPS |
| **Date** | 2026-02-18 |
| **Author** | design-agent |
| **DEFINE** | [DEFINE_FEATURE_STORE_MLOPS.md](./DEFINE_FEATURE_STORE_MLOPS.md) |
| **BRAINSTORM** | [BRAINSTORM_FEATURE_STORE_MLOPS.md](./BRAINSTORM_FEATURE_STORE_MLOPS.md) |
| **Status** | Ready for Build |

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        ATHLETE DATA PLATFORM - MLOPS ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────┐                                                                    │
│  │ STRAVA API  │                                                                    │
│  └──────┬──────┘                                                                    │
│         │                                                                            │
│         ▼                                                                            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                           │
│  │    RAW      │────▶│   BRONZE    │────▶│   SILVER    │                           │
│  │   (ADLS)    │     │  (Delta)    │     │  (Delta)    │                           │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                           │
│                                                  │                                   │
│                      ┌───────────────────────────┼───────────────────────────┐      │
│                      │           FEATURE ENGINEERING LAYER                   │      │
│                      │                           │                           │      │
│                      │    ┌──────────────────────┼──────────────────────┐   │      │
│                      │    │                      ▼                      │   │      │
│                      │    │  ┌─────────────────────────────────────┐   │   │      │
│                      │    │  │         FEATURE STORE (UC)          │   │   │      │
│                      │    │  │  ┌─────────┐ ┌─────────┐ ┌────────┐ │   │   │      │
│                      │    │  │  │activity │ │ weekly  │ │rolling │ │   │   │      │
│                      │    │  │  │features │ │features │ │features│ │   │   │      │
│                      │    │  │  └─────────┘ └─────────┘ └────────┘ │   │   │      │
│                      │    │  └─────────────────┬───────────────────┘   │   │      │
│                      │    └────────────────────┼────────────────────────┘   │      │
│                      └─────────────────────────┼────────────────────────────┘      │
│                                                │                                    │
│                      ┌─────────────────────────┼────────────────────────────┐      │
│                      │              ML TRAINING LAYER                        │      │
│                      │                         │                             │      │
│                      │    ┌────────────────────▼────────────────────┐       │      │
│                      │    │              MLFLOW                      │       │      │
│                      │    │  ┌───────────┐  ┌────────────────────┐  │       │      │
│                      │    │  │Experiments│  │   Model Registry   │  │       │      │
│                      │    │  │  (runs)   │  │      (UC)          │  │       │      │
│                      │    │  └───────────┘  └─────────┬──────────┘  │       │      │
│                      │    └────────────────────────────┼─────────────┘       │      │
│                      └─────────────────────────────────┼─────────────────────┘      │
│                                                        │                            │
│                      ┌─────────────────────────────────┼─────────────────────┐      │
│                      │              INFERENCE LAYER                           │      │
│                      │                                 │                      │      │
│                      │    ┌────────────────────────────▼───────────────────┐ │      │
│                      │    │              BATCH INFERENCE                    │ │      │
│                      │    │  ┌─────────────┐      ┌──────────────────────┐ │ │      │
│                      │    │  │   Models    │─────▶│   GOLD (Predictions) │ │ │      │
│                      │    │  │ (Registered)│      │   athlete_predictions│ │ │      │
│                      │    │  └─────────────┘      └──────────────────────┘ │ │      │
│                      │    └────────────────────────────────────────────────┘ │      │
│                      └───────────────────────────────────────────────────────┘      │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

UNITY CATALOG LAYOUT:
═════════════════════
uc_athlete_data (catalog)
├── bronze (schema)
│   ├── strava_activities
│   ├── strava_athlete
│   └── strava_sub_activity
├── silver (schema)
│   ├── strava_activities
│   └── strava_sub_activity
├── feature_store (schema) ← NEW
│   ├── activity_features
│   ├── athlete_daily_features
│   ├── athlete_weekly_features
│   └── athlete_rolling_features
├── gold (schema) ← NEW
│   ├── athlete_predictions
│   └── athlete_metrics_summary
└── models (UC Model Registry) ← NEW
    ├── time_estimator
    └── overtraining_detector

DABs JOB ORCHESTRATION:
═══════════════════════
strava-pipeline (existing)
├── bronze_load_activities
├── Silver_Activities
├── bronze_load_SubActivity
└── Silver_SubActivity

feature-store-pipeline (NEW)
├── compute_activity_features
├── compute_weekly_features
├── compute_rolling_features
└── run_batch_inference
```

---

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Feature Engineering** | Calcular features de training load, HR zones | PySpark + Databricks FS APIs |
| **Feature Store** | Armazenar features versionadas | Databricks Feature Store + Unity Catalog |
| **Experiment Tracking** | Rastrear runs de treinamento | MLflow |
| **Model Registry** | Versionar e gerenciar modelos | Unity Catalog Model Registry |
| **Batch Inference** | Gerar predições | MLflow + Spark UDF |
| **Job Orchestration** | Agendar pipelines | Databricks Asset Bundles |

---

## Key Decisions

### Decision 1: Feature Store APIs vs Delta Tables Manuais

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-18 |

**Context:** Precisamos armazenar features para ML. Podemos usar Delta tables normais ou Feature Store APIs.

**Choice:** Usar Databricks Feature Store APIs com Unity Catalog.

**Rationale:**
- Versionamento automático de features
- Point-in-time correctness para training
- Lineage completo (features → models)
- APIs de lookup facilitam training e inference

**Alternatives Rejected:**
1. Delta tables manuais - Sem versionamento, JOINs manuais
2. External feature store (Feast) - Complexidade adicional, não integrado

**Consequences:**
- Dependência das APIs do Databricks
- Curva de aprendizado das APIs
- Benefício: Menos código boilerplate

---

### Decision 2: Schema Separado para Feature Store

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-18 |

**Context:** Onde colocar as feature tables no Unity Catalog?

**Choice:** Criar schema `feature_store` dentro do catálogo `uc_athlete_data` existente.

**Rationale:**
- Separação clara de responsabilidades (silver = cleaned, feature_store = ML-ready)
- Governance unificada no mesmo catálogo
- Facilita descoberta de features

**Alternatives Rejected:**
1. Mesmo schema que Silver - Mistura dados operacionais com features
2. Catálogo separado - Fragmenta governance

---

### Decision 3: Granularidades de Features

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-18 |

**Context:** Qual granularidade temporal para as features?

**Choice:** 4 tabelas com granularidades diferentes.

| Table | Grain | Primary Keys |
|-------|-------|--------------|
| `activity_features` | Por atividade | athlete_id, activity_id |
| `athlete_daily_features` | Por dia | athlete_id, activity_date |
| `athlete_weekly_features` | Por semana | athlete_id, week_start |
| `athlete_rolling_features` | Por dia (janelas móveis) | athlete_id, as_of_date |

**Rationale:**
- Diferentes modelos precisam de diferentes granularidades
- Rolling features (CTL/ATL) precisam de cálculo diário
- Weekly features para análise de tendências

---

### Decision 4: HR Zones Calculation

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-18 |

**Context:** Como calcular as zonas de heart rate?

**Choice:** Zonas baseadas em % do Max HR estimado (220 - idade) ou Max HR observado.

```python
ZONES = {
    "zone_1": (0.50, 0.60),  # Recovery
    "zone_2": (0.60, 0.70),  # Aerobic
    "zone_3": (0.70, 0.80),  # Tempo
    "zone_4": (0.80, 0.90),  # Threshold
    "zone_5": (0.90, 1.00),  # VO2max
}
```

**Rationale:** Approach padrão na indústria, não requer teste de lactato.

---

### Decision 5: Training Stress Score (TSS) Estimation

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-02-18 |

**Context:** Como estimar TSS sem dados de power?

**Choice:** Usar pace-based TSS (rTSS) com threshold pace como referência.

```python
def estimate_tss(duration_min: float, pace: float, threshold_pace: float) -> float:
    intensity_factor = threshold_pace / pace  # Inverted because lower pace = faster
    normalized_pace = pace * intensity_factor
    tss = (duration_min * intensity_factor ** 2) / 60 * 100
    return tss
```

**Rationale:** rTSS é o padrão para corrida, threshold pace derivado do histórico.

---

## File Manifest

| # | File | Action | Purpose | Dependencies |
|---|------|--------|---------|--------------|
| 1 | `src/feature_engineering/__init__.py` | Create | Package init | None |
| 2 | `src/feature_engineering/config.py` | Create | Configurações (zones, thresholds) | None |
| 3 | `src/feature_engineering/schemas.py` | Create | Schemas das feature tables | None |
| 4 | `src/feature_engineering/transformations.py` | Create | Funções de cálculo de features | 2, 3 |
| 5 | `src/feature_engineering/feature_store_client.py` | Create | Wrapper para FS APIs | 3 |
| 6 | `src/notebooks/Feature_Activity.py` | Create | Job: activity features | 4, 5 |
| 7 | `src/notebooks/Feature_Weekly.py` | Create | Job: weekly features | 4, 5 |
| 8 | `src/notebooks/Feature_Rolling.py` | Create | Job: rolling features (CTL/ATL) | 4, 5 |
| 9 | `src/ml/__init__.py` | Create | ML package init | None |
| 10 | `src/ml/config.py` | Create | ML configurations | None |
| 11 | `src/ml/time_estimator/train.py` | Create | Training script | 5, 10 |
| 12 | `src/ml/time_estimator/inference.py` | Create | Inference script | 5, 10 |
| 13 | `src/notebooks/Train_Time_Estimator.py` | Create | Job: train model | 11 |
| 14 | `src/notebooks/Batch_Inference.py` | Create | Job: run predictions | 12 |
| 15 | `resources/feature-store-pipeline.yml` | Create | DABs job definition | 6, 7, 8 |
| 16 | `resources/ml-pipeline.yml` | Create | DABs ML job definition | 13, 14 |
| 17 | `tests/test_transformations.py` | Create | Unit tests | 4 |
| 18 | `tests/test_feature_store_client.py` | Create | Unit tests | 5 |

**Total Files:** 18

---

## Code Patterns

### Pattern 1: Feature Store Table Creation

```python
# src/feature_engineering/feature_store_client.py
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
from pyspark.sql import DataFrame

class AthleteFeatureStore:
    """Wrapper for Databricks Feature Store operations."""

    def __init__(self, catalog: str = "uc_athlete_data", schema: str = "feature_store"):
        self.fe = FeatureEngineeringClient()
        self.catalog = catalog
        self.schema = schema

    def create_or_update_table(
        self,
        name: str,
        df: DataFrame,
        primary_keys: list[str],
        timestamp_keys: list[str] | None = None,
        description: str = ""
    ) -> None:
        """Create or update a feature table."""
        full_name = f"{self.catalog}.{self.schema}.{name}"

        # Check if table exists
        try:
            self.fe.get_table(full_name)
            # Table exists, write data
            self.fe.write_table(
                name=full_name,
                df=df,
                mode="merge"
            )
        except Exception:
            # Create new table
            self.fe.create_table(
                name=full_name,
                primary_keys=primary_keys,
                timestamp_keys=timestamp_keys,
                df=df,
                description=description
            )

    def get_training_set(
        self,
        df: DataFrame,
        feature_lookups: list[FeatureLookup],
        label: str
    ):
        """Create training set with point-in-time lookup."""
        return self.fe.create_training_set(
            df=df,
            feature_lookups=feature_lookups,
            label=label,
            exclude_columns=[]
        )
```

### Pattern 2: Training Load Calculations

```python
# src/feature_engineering/transformations.py
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

def calculate_tss(df: DataFrame, threshold_pace_col: str = "threshold_pace") -> DataFrame:
    """Calculate Training Stress Score for running activities."""
    return df.withColumn(
        "intensity_factor",
        F.col(threshold_pace_col) / F.col("pace_min_km")
    ).withColumn(
        "estimated_tss",
        (F.col("moving_time_min") * F.pow(F.col("intensity_factor"), 2)) / 60 * 100
    )

def calculate_ctl_atl(df: DataFrame, athlete_col: str = "athlete_id") -> DataFrame:
    """Calculate Chronic and Acute Training Load using exponential moving average."""
    # Window for rolling calculations
    window_42d = Window.partitionBy(athlete_col).orderBy("activity_date").rowsBetween(-41, 0)
    window_7d = Window.partitionBy(athlete_col).orderBy("activity_date").rowsBetween(-6, 0)

    # CTL (42-day EMA approximation using simple average for MVP)
    df = df.withColumn(
        "ctl_42d",
        F.avg("daily_tss").over(window_42d)
    )

    # ATL (7-day EMA approximation)
    df = df.withColumn(
        "atl_7d",
        F.avg("daily_tss").over(window_7d)
    )

    # TSB (Form)
    df = df.withColumn(
        "tsb",
        F.col("ctl_42d") - F.col("atl_7d")
    )

    # ACWR (Acute:Chronic Workload Ratio)
    df = df.withColumn(
        "acwr",
        F.when(F.col("ctl_42d") > 0, F.col("atl_7d") / F.col("ctl_42d")).otherwise(0)
    )

    return df

def calculate_hr_zones(
    df: DataFrame,
    hr_col: str = "average_heartrate",
    max_hr_col: str = "max_heartrate"
) -> DataFrame:
    """Calculate time in HR zones based on estimated max HR."""
    zones = [
        ("zone_1", 0.50, 0.60),
        ("zone_2", 0.60, 0.70),
        ("zone_3", 0.70, 0.80),
        ("zone_4", 0.80, 0.90),
        ("zone_5", 0.90, 1.00),
    ]

    for zone_name, lower, upper in zones:
        df = df.withColumn(
            f"hr_{zone_name}_pct",
            F.when(
                (F.col(hr_col) / F.col(max_hr_col) >= lower) &
                (F.col(hr_col) / F.col(max_hr_col) < upper),
                1.0
            ).otherwise(0.0)
        )

    return df
```

### Pattern 3: MLflow Training with Feature Store

```python
# src/ml/time_estimator/train.py
import mlflow
from mlflow.models import infer_signature
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

def train_time_estimator(
    training_df,
    target_distance: str = "10k",
    experiment_name: str = "/Shared/athlete-platform/time-estimator"
):
    """Train time estimator model with Feature Store integration."""

    mlflow.set_experiment(experiment_name)
    fe = FeatureEngineeringClient()

    # Define feature lookups
    feature_lookups = [
        FeatureLookup(
            table_name="uc_athlete_data.feature_store.athlete_rolling_features",
            lookup_key=["athlete_id", "as_of_date"],
            feature_names=["ctl_42d", "atl_7d", "pace_trend_30d", "consistency_score"]
        )
    ]

    # Create training set with point-in-time lookup
    training_set = fe.create_training_set(
        df=training_df,
        feature_lookups=feature_lookups,
        label=f"actual_time_{target_distance}",
        exclude_columns=["athlete_id", "as_of_date"]
    )

    training_data = training_set.load_df().toPandas()

    # Split
    X = training_data.drop(columns=[f"actual_time_{target_distance}"])
    y = training_data[f"actual_time_{target_distance}"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    with mlflow.start_run() as run:
        # Train model
        model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        model.fit(X_train, y_train)

        # Evaluate
        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        rmse = np.sqrt(mean_squared_error(y_test, predictions))

        # Log metrics
        mlflow.log_metric("mae_seconds", mae)
        mlflow.log_metric("rmse_seconds", rmse)
        mlflow.log_metric("mae_minutes", mae / 60)

        # Log model with Feature Store
        fe.log_model(
            model=model,
            artifact_path="model",
            flavor=mlflow.sklearn,
            training_set=training_set,
            registered_model_name="uc_athlete_data.models.time_estimator"
        )

        print(f"Model trained. MAE: {mae/60:.2f} minutes")

    return run.info.run_id
```

### Pattern 4: DABs Job Configuration

```yaml
# resources/feature-store-pipeline.yml
resources:
  jobs:
    feature-store-pipeline:
      name: "[${bundle.target}] Feature Store Pipeline"

      tasks:
        - task_key: compute_activity_features
          notebook_task:
            notebook_path: ../src/notebooks/Feature_Activity.py
          job_cluster_key: feature_cluster

        - task_key: compute_weekly_features
          depends_on:
            - task_key: compute_activity_features
          notebook_task:
            notebook_path: ../src/notebooks/Feature_Weekly.py
          job_cluster_key: feature_cluster

        - task_key: compute_rolling_features
          depends_on:
            - task_key: compute_weekly_features
          notebook_task:
            notebook_path: ../src/notebooks/Feature_Rolling.py
          job_cluster_key: feature_cluster

      job_clusters:
        - job_cluster_key: feature_cluster
          new_cluster:
            spark_version: "15.4.x-scala2.12"
            node_type_id: "Standard_DS3_v2"
            num_workers: 1
            spark_conf:
              "spark.databricks.delta.preview.enabled": "true"

      schedule:
        quartz_cron_expression: "0 0 6 * * ?"  # Daily at 6 AM
        timezone_id: "America/Sao_Paulo"
        pause_status: "${var.pause_status}"
```

---

## Data Flow

```text
1. Silver tables updated (activities, sub_activity)
   │
   ▼
2. Feature_Activity.py executes
   │  - Read silver.strava_activities
   │  - Calculate: pace metrics, elevation metrics
   │  - Join sub_activity for HR data
   │  - Calculate: HR zones, efficiency
   │  - Write to: feature_store.activity_features
   │
   ▼
3. Feature_Weekly.py executes
   │  - Read activity_features
   │  - Aggregate by athlete_id, week
   │  - Calculate: weekly volume, monotony, strain
   │  - Write to: feature_store.athlete_weekly_features
   │
   ▼
4. Feature_Rolling.py executes
   │  - Read activity_features
   │  - Calculate rolling windows (7d, 30d, 42d)
   │  - Calculate: CTL, ATL, TSB, ACWR
   │  - Write to: feature_store.athlete_rolling_features
   │
   ▼
5. Train_Time_Estimator.py executes (on-demand or scheduled)
   │  - Load features via Feature Store lookup
   │  - Train XGBoost model
   │  - Log to MLflow
   │  - Register in UC Model Registry
   │
   ▼
6. Batch_Inference.py executes
   │  - Load latest model from registry
   │  - Score batch using Feature Store
   │  - Write predictions to gold.athlete_predictions
```

---

## Feature Table Schemas

### activity_features

```python
ACTIVITY_FEATURES_SCHEMA = {
    "primary_keys": ["athlete_id", "activity_id"],
    "timestamp_keys": ["event_timestamp"],
    "columns": {
        # Keys
        "athlete_id": "STRING",
        "activity_id": "LONG",
        "event_timestamp": "TIMESTAMP",

        # Basic metrics
        "sport_type": "STRING",
        "distance_km": "DOUBLE",
        "moving_time_min": "DOUBLE",
        "elapsed_time_min": "DOUBLE",
        "pace_min_km": "DOUBLE",
        "elevation_gain_m": "DOUBLE",
        "elevation_per_km": "DOUBLE",

        # Training load
        "estimated_tss": "DOUBLE",
        "intensity_factor": "DOUBLE",

        # HR metrics (nullable)
        "avg_hr": "DOUBLE",
        "max_hr": "DOUBLE",
        "hr_zone_1_pct": "DOUBLE",
        "hr_zone_2_pct": "DOUBLE",
        "hr_zone_3_pct": "DOUBLE",
        "hr_zone_4_pct": "DOUBLE",
        "hr_zone_5_pct": "DOUBLE",
        "efficiency_index": "DOUBLE",
    }
}
```

### athlete_rolling_features

```python
ROLLING_FEATURES_SCHEMA = {
    "primary_keys": ["athlete_id", "as_of_date"],
    "timestamp_keys": ["as_of_date"],
    "columns": {
        # Keys
        "athlete_id": "STRING",
        "as_of_date": "DATE",

        # Training load
        "ctl_42d": "DOUBLE",           # Chronic Training Load (Fitness)
        "atl_7d": "DOUBLE",            # Acute Training Load (Fatigue)
        "tsb": "DOUBLE",               # Training Stress Balance (Form)
        "acwr": "DOUBLE",              # Acute:Chronic Workload Ratio

        # Trends
        "pace_trend_30d": "DOUBLE",    # Pace improvement (negative = faster)
        "distance_trend_30d": "DOUBLE", # Volume trend
        "consistency_score": "DOUBLE", # % of expected training days

        # Aggregates
        "activities_30d": "INT",
        "total_distance_30d_km": "DOUBLE",
        "avg_pace_30d": "DOUBLE",
        "best_pace_30d": "DOUBLE",

        # Risk indicators
        "training_monotony_7d": "DOUBLE",
        "training_strain_7d": "DOUBLE",
        "rest_days_14d": "INT",
        "is_overtraining_risk": "BOOLEAN",
    }
}
```

---

## Integration Points

| External System | Integration Type | Authentication |
|-----------------|-----------------|----------------|
| Unity Catalog | Spark SQL | Workspace credentials |
| Feature Store | Python SDK | Workspace credentials |
| MLflow | Python SDK | Workspace credentials |
| Model Registry | Unity Catalog | Workspace credentials |
| Azure Data Lake | abfss:// | Service Principal |

---

## Testing Strategy

| Test Type | Scope | Files | Tools | Coverage Goal |
|-----------|-------|-------|-------|---------------|
| Unit | Transformation functions | `tests/test_transformations.py` | pytest | 80% |
| Unit | Feature Store client | `tests/test_feature_store_client.py` | pytest + mocks | 80% |
| Integration | Feature pipeline | `tests/test_feature_pipeline.py` | pytest + Databricks Connect | Key paths |
| E2E | Full flow | Manual on Databricks | - | Happy path |

### Test Examples

```python
# tests/test_transformations.py
import pytest
from pyspark.sql import SparkSession
from src.feature_engineering.transformations import calculate_tss, calculate_ctl_atl

@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.appName("tests").getOrCreate()

def test_calculate_tss(spark):
    """TSS should be positive for valid activities."""
    data = [
        ("athlete1", 1, 45.0, 5.5, 5.0),  # 45 min, 5.5 min/km, threshold 5.0
    ]
    df = spark.createDataFrame(data, ["athlete_id", "activity_id", "moving_time_min", "pace_min_km", "threshold_pace"])

    result = calculate_tss(df)
    tss = result.select("estimated_tss").collect()[0][0]

    assert tss > 0
    assert tss < 200  # Reasonable range

def test_calculate_acwr_safe_range(spark):
    """ACWR between 0.8 and 1.3 should not flag overtraining risk."""
    # Test implementation
    pass
```

---

## Error Handling

| Error Type | Handling Strategy | Retry? |
|------------|-------------------|--------|
| Missing HR data | Set HR features to NULL, continue | No |
| Feature Store API error | Log error, raise exception | Yes (3x) |
| Model training failure | Log to MLflow as failed run | No |
| Data quality failure | Write to rejects table, continue | No |
| Cluster timeout | Job retry via DABs | Yes |

---

## Configuration

```python
# src/feature_engineering/config.py
from dataclasses import dataclass

@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""

    # Unity Catalog
    catalog: str = "uc_athlete_data"
    feature_schema: str = "feature_store"
    gold_schema: str = "gold"

    # HR Zones (% of max HR)
    hr_zones: dict = None

    # Training load
    default_threshold_pace: float = 5.5  # min/km
    ctl_window_days: int = 42
    atl_window_days: int = 7

    # Risk thresholds
    acwr_risk_threshold: float = 1.5
    monotony_risk_threshold: float = 2.0

    def __post_init__(self):
        if self.hr_zones is None:
            self.hr_zones = {
                "zone_1": (0.50, 0.60),
                "zone_2": (0.60, 0.70),
                "zone_3": (0.70, 0.80),
                "zone_4": (0.80, 0.90),
                "zone_5": (0.90, 1.00),
            }

@dataclass
class MLConfig:
    """Configuration for ML training."""

    experiment_base_path: str = "/Shared/athlete-platform"
    model_registry_prefix: str = "uc_athlete_data.models"

    # Time estimator
    time_estimator_targets: list = None

    def __post_init__(self):
        if self.time_estimator_targets is None:
            self.time_estimator_targets = ["5k", "10k", "21k", "42k"]
```

---

## Security Considerations

- **Data Isolation**: Features particionadas por `athlete_id`, modelo single-tenant
- **Unity Catalog ACLs**: Somente owner tem acesso ao schema `feature_store`
- **Model Access**: Modelos registrados com permissões restritas
- **No PII in Features**: Features são métricas derivadas, não dados pessoais
- **Audit Logging**: Unity Catalog logs acessos automaticamente

---

## Observability

| Aspect | Implementation |
|--------|----------------|
| **Logging** | Structured logging via `spark.log4j` + custom metrics |
| **Metrics** | MLflow metrics para training, Spark metrics para jobs |
| **Monitoring** | Job runs no Databricks Workflows |
| **Alerting** | Job failure notifications (configurar em DABs) |
| **Lineage** | Unity Catalog lineage graph automático |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-18 | design-agent | Initial version |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_FEATURE_STORE_MLOPS.md`
