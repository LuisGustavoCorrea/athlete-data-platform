# Feature Store Quick Reference

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 2, 4, 8, 10, 11, 13, 14)

## The FTI Pipeline Pattern

| Pipeline | Input | Output | When runs |
|----------|-------|--------|-----------|
| **Feature Pipeline** | Raw data | Feature groups in Feature Store (MITs only) | On schedule or event |
| **Training Pipeline** | Feature view (features + labels) | Trained model in registry | On demand or schedule |
| **Inference Pipeline** | Features + Model | Predictions | On request or schedule |

## Data Transformation Taxonomy

```
MIT (Model-Independent):  computed in Feature Pipeline → stored in Feature Store
                          Example: CTL, ACWR, rolling pace, windowed aggregations

MDT (Model-Dependent):    computed in BOTH Training AND Inference (same code!)
                          Example: normalization, one-hot encoding, embeddings

ODT (On-Demand):          computed at INFERENCE TIME and in batch logging (same code!)
                          Example: current_hr/threshold, real-time pace deviation
```

## Feature Store Terminology

```
Feature Group   = Table of features with primary key + event_time
Feature View    = Metadata-only JOIN of feature groups → training or inference input
Feature Vector  = Row of features for one entity at one point in time
Training Set    = Point-in-time snapshot of features + labels (versioned)
Online Store    = Row-oriented KV store, <10ms lookup (RonDB, DynamoDB, Redis)
Offline Store   = Columnar lakehouse (Delta, Iceberg, Hudi) for training + batch
SCD Type 0      = No event_time → immutable reference data
SCD Type 2      = event_time + offline only → batch ML
SCD Type 4      = event_time + online+offline → real-time ML
```

## Model Architecture Selection Rule

```
< 10M rows    → XGBoost (decision trees) — almost always wins
10M–100M rows → benchmark both
> 100M rows   → Neural Networks
```

## ML System Types

```
BATCH                REAL-TIME              LLM / AGENTIC
──────               ─────────              ──────────────
Scheduled            Request-triggered      Event-triggered
Minutes/hours        Milliseconds           Seconds
Spark/Python         REST API (FastAPI)     RAG pipeline
Offline store        Online store (SCD 4)   Vector DB + FS
Gold table output    HTTP response          Generated text
```

## ASOF LEFT JOIN (Point-in-Time Under the Hood)

```sql
-- Starts from label table, pulls feature values where feature.event_ts <= label.event_ts
SELECT label.target, rolling.ctl_42d, activity.pace_min_km
FROM athlete_labels_fg AS label
ASOF LEFT JOIN athlete_rolling_fg AS rolling
    ON label.athlete_id = rolling.athlete_id
    AND rolling.as_of_date <= label.race_date    -- ← no future values!
ASOF LEFT JOIN activity_fg AS activity
    ON label.athlete_id = activity.athlete_id
    AND activity.event_time <= label.race_date
```

## Training Set Creation (Databricks)

```python
from databricks.feature_engineering import FeatureLookup

training_set = fe.create_training_set(
    df=labels_df,                           # entity keys + labels + event timestamps
    feature_lookups=[
        FeatureLookup(
            table_name="catalog.fs.athlete_rolling_features",
            lookup_key=["athlete_id"],
            timestamp_lookup_key="race_date",   # ← point-in-time key (CRITICAL)
            feature_names=["ctl_42d", "acwr", "pace_trend_30d"]
        )
    ],
    label="target_time_seconds"
)
```

## Online Inference Feature Vector

```python
features = feature_view.get_feature_vector(
    serving_keys={"athlete_id": "001"},        # → precomputed from online store
    passed_features={"current_hr": 165},       # → ODT already computed by caller
    request_parameters={"ts": "2024-06-15"}    # → for ODT computation in serving code
)
```

## NannyML: Model Monitoring Without Labels

```python
# Classification (CBPE) — fit on test set, estimate in inference pipeline
cbpe = nml.performance_estimation.CBPE(
    y_pred_proba="proba", y_pred="pred", y_true="label",
    timestamp_column_name="ts", metrics=["roc_auc", "f1"], chunk_size="7d"
)
cbpe.fit(reference_data)      # ← in training pipeline
cbpe.estimate(inference_data) # ← in inference pipeline (no labels needed!)

# Regression (DLE)
dle = nml.performance_estimation.DLE(
    feature_column_names=features, y_pred="pred", y_true="actual",
    metrics=["mae", "rmse"], chunk_size="7d"
)
```

## Feature Pipeline Orchestration

```
Modal (serverless):   @app.function(schedule=modal.Period(days=1), image=image, gpu="any")
Databricks Workflows: resources/feature-store-pipeline.yml (DABs)
Airflow:              DAG with PythonOperator
```

## ML Testing Pyramid for AI Systems

```
PRODUCTION ─────────────────────────────
    │  SLO / KPI Monitoring (online)
    │  Model Deployment Tests (blue/green, A/B) (online)
    │  Model Validation: perf + bias slices (offline)
    │  Integration Tests: e2e pipeline (offline)
    │  Data Validation: schema, ranges (offline)
    │  Unit Tests: feature functions (offline)
DEV ────────────────────────────────────
```

## Lineage Chain

```
Data Source → Feature Group → Feature View → Training Dataset → Model → Deployment → Prediction
```

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Monolithic ML script | Can't scale/test independently | Use FTI pipelines |
| MDTs computed differently in train vs serve | Training-serving skew | Single shared function |
| No event_time on feature groups | Can't do point-in-time | Always set event_time |
| Append mode feature writes | Duplicates accumulate | Use merge/upsert |
| Recompute features at inference | Skew + duplicated logic | Pre-compute in feature pipeline |
| No performance gate in training | Bad models reach production | Always assert metrics before registering |
| PSI > 0.25 → immediate retrain | Might be data quality issue | Investigate root cause first |
