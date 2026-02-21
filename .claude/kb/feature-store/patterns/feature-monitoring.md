# Pattern: Feature Monitoring and Drift Detection

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 14)

## Two Pillars of ML Observability

The book defines observability as:

```
OBSERVABILITY = METRICS + LOGS

METRICS → Prometheus scraping → dashboards, autoscaling
LOGS    → feature monitoring, model monitoring, debugging
```

---

## Why Monitor Features?

Models degrade silently when the world changes. Feature monitoring catches this early:

```
Data changes → Feature distribution shifts → Model predictions degrade → Business impact

Catch here ↑ before it reaches business impact
```

---

## Log Store Architecture

The book describes what to log and where:

```
Inference Pipeline logs:
  1. Untransformed features     → feature monitoring (drift detection)
  2. Transformed features       → model monitoring (SHAP, debugging)
  3. Inference helper columns   → analysis slices (e.g., activity_type)
  4. Predictions                → prediction drift detection

Log stores:
  - Lakehouse (Delta/Iceberg)   → batch analysis, long-term history
  - Online feature group + TTL  → real-time monitoring dashboards
  - Document store              → agent traces, LLM logs
```

---

## Types of Drift (from Ch. 14)

| Type | What Changes | Notation | Detection |
|------|-------------|---------|-----------|
| **Data ingestion drift** | New data stops arriving | N(X) vs F(X) | Freshness / count checks |
| **Feature drift** | Feature distributions shift | I(X) vs P(X) | Statistical tests |
| **Concept drift** | Relationship P(Y\|X) changes | Predictions vs outcomes | Performance monitoring |
| **Prediction drift** | Model output distribution shifts | Q(ŷ) vs P(y) | Output histogram |
| **Label shift** | Label distribution changes | P(Y) changes | Compare label stats |
| **KPI degradation** | Business metric drops | Application metric | Business dashboards |

---

## Statistical Drift Detection Methods

### Univariate (per-feature) Methods

| Method | Formula / Use | Good For |
|--------|-------------|---------|
| **KL Divergence** | `Σ P(x) * log(P(x)/Q(x))` | Continuous distributions |
| **Wasserstein Distance** | Earth mover's distance | Continuous, robust |
| **KS Test** | Max diff in CDFs | Any distribution |
| **L-infinity** | `max|P(x) - Q(x)|` | Simple, interpretable |
| **Deviation from mean** | `(current_mean - ref_mean) / ref_std` | Numerical features |
| **PSI** | `Σ (A - E) * ln(A/E)` | Legacy, still common |

```python
# Kolmogorov-Smirnov Test
from scipy import stats

ks_stat, p_value = stats.ks_2samp(training_distribution, current_distribution)
if p_value < 0.05:
    alert("Feature drift detected: p_value={p_value:.4f}")

# PSI thresholds (legacy):
# PSI < 0.1:    No drift
# PSI 0.1-0.25: Moderate drift → investigate
# PSI > 0.25:   Significant drift → retrain or redesign
```

### Multivariate Drift Detection (NannyML)

```python
import nannyml as nml

# Method 1: PCA Data Reconstruction (detects multivariate drift)
dc = nml.DataReconstructionDriftCalculator(
    column_names=feature_columns,
    timestamp_column_name="event_time",
    chunk_size="7d"
)
dc.fit(reference)
results = dc.calculate(analysis)
results.plot(kind="drift").show()

# Method 2: Domain Classifier (train binary classifier to distinguish reference vs analysis)
# If ROC AUC >> 0.5, the classifier can tell datasets apart → drift detected
dc2 = nml.DomainClassifierCalculator(
    feature_column_names=feature_columns,
    timestamp_column_name="event_time",
    chunk_size="7d"
)
dc2.fit(reference)
results2 = dc2.calculate(analysis)
```

---

## Model Performance Monitoring Without Outcomes

The book covers two NannyML methods for estimating model performance when ground truth labels aren't available yet (delayed or never available):

### CBPE — Confidence-Based Performance Estimation
For **classification** models. Uses predict_proba to estimate performance.

```python
import nannyml as nml

# 1. Fit on test set DURING TRAINING PIPELINE
cbpe = nml.performance_estimation.CBPE(
    y_pred_proba="y_pred_proba",
    y_pred="y_pred",
    y_true="is_fraud",
    timestamp_column_name="event_time",
    metrics=["roc_auc", "f1", "precision", "recall"],
    chunk_size="7d",
    problem_type="binary_classification"
)
cbpe.fit(reference_data)  # ← fit on test set, save estimator

# 2. Use in INFERENCE PIPELINE to estimate performance without labels
estimated_perf = cbpe.estimate(inference_data_with_predictions)
# Returns: estimated ROC AUC, F1, precision, recall per chunk
```

### DLE — Direct Loss Estimation
For **regression** models. Uses a meta-model to predict the model's error.

```python
# DLE for regression (e.g., time estimator model)
dle = nml.performance_estimation.DLE(
    feature_column_names=feature_columns,
    y_pred="predicted_time_seconds",
    y_true="actual_time_seconds",
    timestamp_column_name="prediction_date",
    metrics=["mae", "rmse"],
    chunk_size="7d"
)
dle.fit(reference)  # fit on test set in training pipeline
estimated_error = dle.estimate(inference_data)
```

---

## Databricks Lakehouse Monitoring

```python
from databricks.lakehouse_monitoring import create_monitor, MonitorProfileType

# Set up monitoring on feature table
create_monitor(
    table_name="uc_athlete_data.feature_store.athlete_rolling_features",
    profile_type=MonitorProfileType.TIME_SERIES,
    timestamp_col="as_of_date",
    granularities=["1 day", "1 week"],
    output_schema_name="uc_athlete_data.monitoring",
    baseline_table_name="uc_athlete_data.feature_store.athlete_rolling_features_baseline"
)
# → Creates drift_metrics and profile_metrics tables automatically
```

---

## Agent / LLM Monitoring (from Ch. 14)

### Traces and Spans
```python
# Agent traces: hierarchical spans (Opik framework)
import opik

@opik.track
def agent_run(user_query: str) -> str:
    with opik.span("feature_lookup"):
        features = feature_store.get_feature_vector(...)
    with opik.span("llm_call"):
        response = llm.generate(prompt, features)
    with opik.span("guardrail_check"):
        safe_response = guardrail.check(response)
    return safe_response

# Traces stored → error analysis taxonomy:
# - Instruction-following errors
# - Hallucination / factuality errors
# - Format errors
# - Context retrieval errors
```

### Guardrails
```python
# Input + output detectors
def apply_guardrails(user_input: str, model_output: str):
    # Input detector: ALLOW / BLOCK / SANITIZE
    input_decision = input_guardrail.check(user_input)
    if input_decision == "BLOCK":
        return "Request blocked by content policy"
    if input_decision == "SANITIZE":
        user_input = input_guardrail.sanitize(user_input)

    response = model.generate(user_input)

    # Output detector
    output_decision = output_guardrail.check(response)
    if output_decision == "BLOCK":
        return "Response blocked by content policy"
    return response
```

### LLM Metrics (for autoscaling)
The book is specific: use **token throughput** and **average token latency** — NOT request throughput:
```
token_throughput     = total_tokens_generated / time_window
avg_token_latency    = total_generation_time / total_tokens_generated

→ Use these as autoscaling signals (not requests/sec)
```

---

## When to Retrain vs. Redesign

```
Small drift detected (PSI 0.1-0.25 or KS p>0.01)
  └─ Retrain with recent data (incremental drift)

Large drift detected (PSI > 0.25 or KS p<0.01)
  └─ Investigate root cause:
       ├─ Data quality issue  → Fix pipeline, no retrain needed
       ├─ Behavioral change   → Add new features, then retrain
       └─ Concept drift       → Redesign features / model architecture

Estimated performance drops (CBPE / DLE)
  └─ Immediate retrain trigger

Guardrail hit rate increasing
  └─ Investigate LLM behavior, update prompt / fine-tune
```

---

## Athlete Platform Monitoring Checklist

| Feature | What to Monitor | Alert Threshold |
|---------|----------------|-----------------|
| `pace_min_km` | Distribution shift (KS) | p < 0.05 |
| `ctl_42d` | Monthly average drop | >20% drop vs 30d avg |
| `acwr` | Values outside [0.5, 1.5] | >5% records out of range |
| `estimated_tss` | Null rate | >10% nulls |
| `avg_hr` | Coverage rate | <50% activities with HR |
| `predicted_time_s` | Prediction drift | KS p < 0.05 |
| Feature pipeline | Row count per run | <50% of expected rows |
