# MLOps Principles for ML Systems

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 2, 13)

## MLOps Redefined

> "MLOps is about **automated testing, versioning, and monitoring** of ML artifacts."
> — Jim Dowling

Not about infrastructure complexity — about disciplined engineering applied to ML.

## The Three Pillars

```
┌─────────────────────────────────────────────────────────┐
│                    MLOPS PILLARS                         │
├─────────────────┬──────────────────┬────────────────────┤
│    TESTING      │    VERSIONING    │    MONITORING      │
├─────────────────┼──────────────────┼────────────────────┤
│ Unit tests      │ Feature versions │ Feature drift      │
│ Data validation │ Model versions   │ Prediction drift   │
│ Model eval      │ Dataset versions │ Data quality       │
│ A/B testing     │ Pipeline versions│ Retraining alerts  │
└─────────────────┴──────────────────┴────────────────────┘
```

---

## Testing Strategy: The ML Testing Pyramid for AI Systems

The book defines a specific **offline + online testing pyramid** for ML systems:

```
PRODUCTION ──────────────────────────────────────────────
             ┌─────────────────────────────┐
             │    SLO / KPI Monitoring     │  ← online
             ├─────────────────────────────┤
             │  Model Deployment Tests     │  ← online (blue/green, A/B)
             ├─────────────────────────────┤
             │   Model Validation          │  ← offline (perf + bias)
             ├─────────────────────────────┤
             │  Integration Tests          │  ← offline (pipeline e2e)
             ├─────────────────────────────┤
             │   Data Validation           │  ← offline (schema, ranges, nulls)
             ├─────────────────────────────┤
             │   Unit Tests                │  ← offline (feature functions)
             └─────────────────────────────┘
DEV ─────────────────────────────────────────────────────
```

### Layer 1: Unit Tests (Feature Pipeline)
```python
# Test feature functions in isolation with sample data
import pandas as pd
from src.feature_functions import estimated_tss, pace_min_km

def test_tss_positive():
    df = pd.read_csv("tests/sample_activities.csv")
    result = estimated_tss(df["pace_min_km"], threshold_pace=5.0, df["duration_s"])
    assert (result > 0).all(), "TSS must always be positive"

def test_pace_min_km():
    assert abs(pace_min_km(10.0, 3000) - 5.0) < 0.01
```

### Layer 2: Data Validation (Feature Pipeline)
```python
# Mock data source in tests — use sample CSV in version control
# Great Expectations integration with Hopsworks feature groups:

fg.save_expectation_suite(
    expectation_suite=ExpectationSuite(
        expectations=[
            ExpectColumnValuesToBeBetween("pace_min_km", min_value=2.0, max_value=20.0),
            ExpectColumnValuesToNotBeNull("athlete_id"),
            ExpectColumnValuesToNotBeNull("distance_km"),
        ],
        meta={"ingestion_policy": "STRICT"}  # STRICT = reject on fail; ALWAYS = insert always
    )
)
```

### Layer 3: Integration Tests (Full Pipeline)
```python
# Run full feature pipeline with sample data, assert outputs
def test_feature_pipeline_integration():
    run_feature_pipeline(start_time=SAMPLE_START, end_time=SAMPLE_END)
    result_df = spark.table("test_catalog.feature_store.activity_features")
    assert result_df.count() > 0
    assert result_df.filter(col("ctl_42d").isNull()).count() == 0
```

### Layer 4: Model Validation (Training Pipeline)
```python
# Gate: only register model if performance is above threshold
# AND passes bias tests on evaluation slices
metrics = evaluate_model(model, X_test, y_test)
assert metrics["mae_minutes"] < 3.0, f"MAE too high: {metrics['mae_minutes']}"

# Bias test: check that model is fair across population slices
for slice_col, slice_val in [("activity_type", "run"), ("activity_type", "ride")]:
    slice_df = test_df.filter(col(slice_col) == slice_val)
    slice_mae = evaluate_model(model, slice_df)["mae_minutes"]
    assert slice_mae < 5.0, f"Bias detected for {slice_col}={slice_val}: MAE={slice_mae}"

if all_tests_pass:
    mlflow.register_model(model_uri, "uc_athlete_data.models.time_estimator")
```

### Layer 5: Model Deployment Tests (Blue/Green vs A/B)

**Blue/Green Test** (zero risk to users):
```
Blue (production): receives 100% traffic
Green (challenger): receives Y% COPY of traffic
→ Compare prediction logs, no users affected
→ Promote green to blue when metrics match or improve
```

**A/B Test** (tied to KPIs):
```
Production model: X% of users
Challenger model: Y% of users
→ Measure actual business KPI (completion rate, user engagement)
→ More risk, more signal
```

### Layer 6: Evals for LLM Agents
```python
# Eval dataset: {eval_id, task, prompt, expected_response}
# Evaluator scores: {eval_id, score, reasoning}
# LLM-as-a-judge for subjective tasks

eval_dataset = [
    {"eval_id": 1, "task": "explain_training_load",
     "prompt": "Why was my TSS high this week?",
     "expected_response": "Your TSS was high due to..."}
]

for eval in eval_dataset:
    response = agent.run(eval["prompt"])
    score = llm_judge.evaluate(response, eval["expected_response"])
    # Score: 0-5, with reasoning
```

---

## CI/CD Workflow for ML Systems

```
Dev Branch (local testing)
    │
    ▼ pull request
Staging Environment
    │  → unit tests
    │  → integration tests
    │  → model validation
    │  → (human review)
    ▼ merge to main
Production Environment
    │  → blue/green deployment
    │  → A/B tests (if configured)
    │  → monitoring enabled
```

### Automatic Containerization
- **Modal**: per-function containers via decorators — `@app.function(image=image, gpu="any")`
- **Hopsworks Jobs**: reusable environments + job definitions (separate container from code)
- **Databricks**: cluster configuration in `resources/` YAML files (DABs)

---

## Versioning Strategy

```
Feature Group v1 → trained Model v1 → predictions
Feature Group v2 → trained Model v2 → predictions (new)
                                    ↗
               Model v1 still serving (safe rollback)
```

**Rule:** A specific model version is linked to the feature version used to train it.

### What to Version
| Artifact | How | Why |
|---------|-----|-----|
| Feature Groups | Integer version in name | Schema evolution |
| Feature Views | Integer version | Feature set changes |
| Training Data | `training_dataset_version` in model metadata | Reproducibility |
| Models | MLflow registered model versions | Rollback |
| Pipelines | Git commit SHA | Traceability |

### Reproducibility: training_dataset_version
```python
# Stored in model registry at training time
mlflow.log_param("training_dataset_version", feature_view.get_latest_training_dataset().version)
mlflow.log_param("feature_group_version", fg.version)
mlflow.log_param("random_seed", RANDOM_SEED)
# → Enables exact reproduction of training data months later
```

### In Practice (Databricks)
```python
# Model registered with feature lineage
fe.log_model(
    model=model,
    training_set=training_set,  # ← records feature version used
    registered_model_name="uc_athlete_data.models.time_estimator"
)
# → Unity Catalog tracks: model v2 used activity_features v3
```

---

## Monitoring: When to Retrain vs. Redesign

| Signal | Action |
|--------|--------|
| Feature drift (PSI 0.1-0.25) | Retrain with recent data |
| Feature drift (PSI > 0.25) | Investigate root cause |
| Prediction drift | Investigate + retrain |
| Performance degradation (MAE increases) | Retrain immediately |
| New data source added | Retrain with expanded features |
| Concept drift (world fundamentally changed) | Redesign features / architecture |

### Feature Drift Detection
```python
# Compare current distribution vs training distribution
from databricks.lakehouse_monitoring import create_monitor

create_monitor(
    table_name="uc_athlete_data.feature_store.athlete_rolling_features",
    profile_type=TimeSeries(timestamp_col="as_of_date", granularities=["1 day"]),
    output_schema_name="uc_athlete_data.monitoring"
)
```
