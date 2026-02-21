# FTI Architecture: Feature / Training / Inference Pipelines

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 2)

## Core Idea

Any ML system can be decomposed into **three independent pipelines** connected by a shared stateful layer:

```
RAW DATA
   │
   ▼
┌─────────────────────────────────────────┐
│           FEATURE PIPELINE              │
│  Transform raw data → features/labels   │
└───────────────────┬─────────────────────┘
                    │ writes
                    ▼
         ┌──────────────────┐
         │  FEATURE STORE   │  ← shared stateful layer
         │ (offline store)  │
         └──────┬───────────┘
                │ reads
    ┌───────────┼───────────────────┐
    ▼                               ▼
┌──────────────────┐    ┌───────────────────────┐
│ TRAINING PIPELINE│    │  INFERENCE PIPELINE    │
│ features/labels  │    │  features + model      │
│ → trained model  │    │  → predictions         │
└──────────┬───────┘    └───────────┬────────────┘
           │ registers              │ reads
           ▼                        │
  ┌────────────────┐                │
  │ MODEL REGISTRY │────────────────┘
  └────────────────┘
```

## MVPS: Minimal Viable Prediction Service

The book prescribes this development methodology for building ML systems:

```
1. Define prediction problem + KPI
2. Identify data sources
3. Build feature pipeline → feature store
4. Build training pipeline → model registry
5. Build inference pipeline → predictions
6. Build UI (Streamlit/Gradio) for user-facing predictions
7. Monitor and iterate
```

> "Start with the data problem, not the algorithm. Start with the MVPS and iterate."
> — Jim Dowling

---

## Data Transformation Taxonomy (from the book)

The book defines three categories of transformations that appear throughout all three pipelines:

### MITs — Model-Independent Transformations
- **What:** Feature computations that can be reused across multiple models
- **When computed:** In the **Feature Pipeline** — once, stored in feature store
- **Examples:** windowed aggregations, counts, RFM scores, CTL/ATL, rolling pace
- **Rule:** Any transform that doesn't depend on model architecture is a MIT

### MDTs — Model-Dependent Transformations
- **What:** Transforms specific to a model's expectations
- **When computed:** In BOTH **Training Pipeline** AND **Inference Pipeline** (risk of skew!)
- **Examples:** one-hot encoding categorical features, min-max normalization, embedding lookups
- **Critical:** Must use identical code in training and inference — even one difference causes skew

```python
# MDT Example: must run same code in training AND serving
def normalize_features(df):
    df["ctl_42d_norm"] = (df["ctl_42d"] - MEAN_CTL) / STD_CTL
    return df
```

### ODTs — On-Demand Transformations
- **What:** Transforms that require request-time data not available in feature store
- **When computed:** In **Inference Pipeline** (online) AND **Feature Pipeline** (batch logging)
- **Examples:** current HR / threshold HR ratio, real-time pace deviation, request IP geolocation
- **Rule:** Use the **same function** in both places to avoid skew

```python
# ODT Example: same function used in online inference and batch logging
def compute_pace_deviation(current_pace_min_km, historical_avg_pace):
    return (current_pace_min_km - historical_avg_pace) / historical_avg_pace
```

---

## Feature Functions Pattern

Inspired by Apache Hamilton — one function per feature, testable and reusable:

```python
# feature_functions.py
def pace_min_km(distance_km: float, elapsed_time_s: float) -> float:
    """Minutes per km pace."""
    return (elapsed_time_s / 60) / distance_km

def elevation_per_km(elevation_gain_m: float, distance_km: float) -> float:
    """Elevation gain per km."""
    return elevation_gain_m / distance_km

def estimated_tss(pace_min_km: float, threshold_pace: float, duration_s: float) -> float:
    """Training Stress Score approximation."""
    intensity_factor = threshold_pace / pace_min_km
    tss = (duration_s / 3600) * intensity_factor ** 2 * 100
    return tss

# Unit-testable:
def test_pace_min_km():
    result = pace_min_km(distance_km=10.0, elapsed_time_s=3000)
    assert abs(result - 5.0) < 0.01  # 5.0 min/km
```

---

## Framework Selection Guide

| Data Scale | Recommended Framework | Use Case |
|-----------|----------------------|---------|
| < 1 GB | **Pandas** | Athlete dataset, small experiments |
| 10s GB | **Polars** | Larger athlete history, faster local |
| TBs | **PySpark** | Organization-scale, Databricks clusters |
| Streaming | **Feldera / Flink** | Real-time feature computation |

---

## Pipeline Classes (from the book)

### Feature Pipeline Classes
- **Batch Feature Pipeline**: scheduled, reads time range, writes to offline store
- **Streaming Feature Pipeline**: real-time, reads events, writes to online store

### Training Pipeline Classes
- **Batch Training Pipeline**: reads offline store, trains, registers model
- **Continuous Training Pipeline**: triggered by drift or schedule

### Inference Pipeline Classes
- **Batch Inference Pipeline**: scheduled, reads offline features, writes predictions
- **Online Inference Pipeline**: REST API, reads online store, returns prediction in <100ms
- **Agentic Inference Pipeline**: RAG, reads vector DB + feature store, calls LLM

---

## Why Three Pipelines?

| Concern | Monolith | FTI |
|---------|----------|-----|
| Scaling | All-or-nothing | Each pipeline scales independently |
| Technology | Single stack | Each can use best tool (Spark, Pandas, GPU) |
| Teams | Shared codebase | Independent ownership |
| Failures | One failure → all fails | Isolated failure domains |
| Deployment | Redeploy everything | Deploy changed pipeline only |

## Pipeline Contracts

```
Feature Pipeline:
  INPUT:  raw data (files, streams, databases)
  OUTPUT: feature groups in feature store (MITs only)

Training Pipeline:
  INPUT:  feature view (features + labels) from feature store
  OUTPUT: trained model in model registry

Inference Pipeline:
  INPUT:  feature vector from feature store + model from registry
  OUTPUT: predictions (written to DB, API, Gold table)
```

---

## Implementation in Databricks (Athlete Platform)

```
Feature Pipeline  → src/notebooks/Feature_Activity.py
                    src/notebooks/Feature_Rolling.py

Training Pipeline → src/notebooks/Train_Time_Estimator.py

Inference Pipeline → src/notebooks/Batch_Inference.py

Feature Store     → uc_athlete_data.feature_store.*
Model Registry    → uc_athlete_data.models.*
```

## Key Insight: Shared Stateful Layer

The feature store is the **only stateful component** shared between pipelines. This enables:
- Training/serving consistency (same features, same code)
- Point-in-time joins (no data leakage)
- Feature reuse across multiple models
- Decoupled deployment of pipelines
