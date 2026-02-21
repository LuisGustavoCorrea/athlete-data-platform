# ML System Types: Batch, Real-Time, and LLM

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 2, 11)

## Overview

The book defines three types of ML systems, each with different latency, scale, and architecture requirements:

```
┌─────────────────────────────────────────────────────────┐
│          BATCH          │    REAL-TIME    │     LLM      │
├─────────────────────────┼─────────────────┼──────────────┤
│  Minutes to hours       │  Milliseconds   │  Seconds     │
│  Scheduled / triggered  │  On-request     │  On-request  │
│  Offline store only     │  Online store   │  Vector DB   │
│  Spark / Python         │  REST API       │  RAG + FS    │
└─────────────────────────┴─────────────────┴──────────────┘
```

---

## 1. Batch ML Systems

**When to use:** Predictions don't need to be real-time; can be precomputed.

```
Feature Pipeline  →  Feature Store (offline)
Training Pipeline →  Model Registry
Inference Pipeline → reads features + model → writes predictions to Gold table
Scheduler         → triggers daily/hourly
```

**Inference pattern:** Time-range query
```python
# Batch inference: all athletes as of yesterday
batch_data = feature_view.get_batch_data(
    start_time=yesterday,
    end_time=today
)
predictions = model.predict(batch_data)
spark.createDataFrame(predictions).write.mode("overwrite").saveAsTable("gold.predictions")
```

**Scaling with PySpark (for large batch inference):**
```python
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import FloatType
import xgboost as xgb

# Broadcast model path to all workers
broadcasted_model_path = sc.broadcast(model_path)

@pandas_udf(returnType=FloatType())
def pred_udf(features: pd.Series) -> pd.Series:
    xgb_model = xgb.XGBClassifier()
    xgb_model.load_model(broadcasted_model_path.value)
    predictions = xgb_model.predict(pd.DataFrame(features.tolist()).values)
    return pd.Series(predictions, dtype=float)
```

**Examples:** Athlete weekly performance report, churn prediction, demand forecasting.

**Athlete Platform use case:**
```python
# Batch inference writes to gold table daily
spark.table("uc_athlete_data.feature_store.athlete_rolling_features")
    → time_estimator model
    → uc_athlete_data.gold.athlete_predictions
```

---

## 2. Real-Time ML Systems

**When to use:** User-facing predictions need low latency (<100ms).

```
Feature Pipeline  →  Feature Store (offline + online sync, SCD Type 4)
Training Pipeline →  Model Registry
Inference Pipeline → REST API reads from online store → returns prediction
```

### Deployment API vs Model Signature

The book distinguishes two concepts that must NOT be confused:

```
Deployment API (stable, public-facing):
  Input:  serving_keys + request_parameters + passed_features
  Output: prediction + optional metadata

Model Signature (internal, training-time):
  Input:  full feature vector (numpy array / DataFrame)
  Output: prediction (float, int, class)
```

### Three Input Types for Online Inference
```python
features = feature_view.get_feature_vector(
    serving_keys={           # → lookup in online feature store
        "athlete_id": "athlete_001",
    },
    passed_features={        # → features computed by the caller (ODTs at call site)
        "current_hr": 165,
        "current_pace": 5.2
    },
    request_parameters={     # → parameters for ODT computation in serving code
        "ts": "2024-06-15T10:00:00",
        "ip_addr": "192.168.1.1"
    }
)
prediction = model.predict(features)
```

### KServe: Enterprise Model Serving
```
KServe deployment:
  - Transformer container: preprocessing / postprocessing (FastAPI-based)
  - Predictor container: model inference (Triton / vLLM / TorchServe / ONNX Runtime)

Capabilities:
  - A/B testing: route X% traffic to new model
  - Serverless autoscaling (KEDA + Prometheus metrics)
  - Multi-model serving on same GPU
```

**Two feature types in real-time:**
- **Precomputed** (from online store, SCD Type 4): athlete's CTL, historical pace
- **On-demand** (computed at request time, ODTs): current HR, real-time GPS pace

**Athlete Platform (future):**
```
Mobile app → API → online store lookup → model → pace prediction
```

---

## 3. LLM / Agentic Systems

**When to use:** Unstructured data, RAG, agents, semantic search.

```
Feature Pipeline  →  Feature Store + Vector DB (embeddings)
Training Pipeline →  Fine-tuning or prompt engineering
Inference Pipeline → RAG: retrieve context → augment prompt → generate response
```

**Key difference:** Feature store holds structured features; vector DB holds embeddings for semantic retrieval.

**Agentic inference pipeline:**
```
User query → Agent
  → Tool 1: lookup structured features (Feature Store)
  → Tool 2: semantic search (Vector DB)
  → Tool 3: external API
  → Synthesize → LLM → response
```

**Athlete Platform (future):**
```
"Why was my training load high this week?" →
  LLM retrieves athlete features (CTL, ACWR, sessions) → generates explanation
```

---

## Inference Pipeline Types

| Type | Trigger | Feature Source | Output | Latency |
|------|---------|---------------|--------|---------|
| **Batch** | Schedule | Offline store, time range | Gold table | Minutes |
| **Batch (entity)** | Trigger | Offline store, latest per entity | Gold table | Minutes |
| **Online REST** | HTTP request | Online store + passed | HTTP response | <100ms |
| **Streaming** | Event | Kafka/Kinesis + feature store | Feature group | Seconds |
| **Embedded** | In-process | Local file | Direct call | <1ms |

### Embedded Models (for edge / high-performance)
```python
# Load model from local disk, no network calls
import joblib
model = joblib.load("/local/model.pkl")
prediction = model.predict(features)  # sub-millisecond
```

---

## Choosing the Right System

| Question | Batch | Real-Time | LLM |
|----------|-------|-----------|-----|
| Latency requirement? | >1 min OK | <100ms | 1-5s OK |
| Prediction trigger? | Schedule | User request | User query |
| Data type? | Tabular | Tabular | Text/unstructured |
| Scale? | Millions/day | Thousands/sec | Thousands/day |
| Features precomputable? | Yes | Most | No (RAG) |

**Athlete Platform roadmap:**
- **Now**: Batch (daily predictions, training load)
- **Phase 2**: Real-time (live pace coaching during run)
- **Phase 3**: LLM (natural language training insights)
