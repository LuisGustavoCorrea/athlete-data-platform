# Pattern: Inference Pipeline

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 11)

## Definition

An Inference Pipeline is a program that:
- **Input**: feature vector from feature store + trained model from registry
- **Output**: predictions (written to Gold table, API response, event stream)
- **Key principle**: Deployment API is stable and public; model signature is internal and can change

---

## Batch Inference

### Time-Range Query (most common)
```python
# Get all features for all athletes in a time window
batch_data = feature_view.get_batch_data(
    start_time=yesterday,
    end_time=today
)
predictions = model.predict(batch_data[feature_columns])
spark.createDataFrame(zip(batch_data["athlete_id"], predictions),
                      ["athlete_id", "predicted_time_s"]) \
     .write.mode("overwrite").saveAsTable("uc_athlete_data.gold.predictions")
```

### Entity Query (latest features per entity)
```python
# Get the most recent features for specific athletes
batch_data = feature_view.get_batch_data(
    latest_features=True,
    entity_ids={"athlete_id": ["athlete_001", "athlete_002"]}
)
```

### Spine DataFrame (custom entity + timestamp list)
```python
# Custom list of (entity, timestamp) pairs — for evaluation or A/B tests
spine_df = spark.createDataFrame([
    ("athlete_001", "2024-06-15"),
    ("athlete_002", "2024-06-15"),
], ["athlete_id", "prediction_date"])

batch_data = feature_view.get_batch_data(spine=spine_df)
```

---

## Scaling Batch Inference with PySpark

For large athlete datasets (millions of records), use Pandas UDF:

```python
from pyspark.sql.functions import pandas_udf, struct, col
from pyspark.sql.types import FloatType
import xgboost as xgb
import pandas as pd

# Broadcast model path to all workers (avoids loading model once per row)
broadcasted_model_path = sc.broadcast(model_path)

@pandas_udf(returnType=FloatType())
def pred_udf(features: pd.Series) -> pd.Series:
    """Pandas UDF: batch prediction within each Spark partition."""
    xgb_model = xgb.XGBClassifier()
    xgb_model.load_model(broadcasted_model_path.value)
    # features is a Series of dicts — convert to DataFrame
    feature_df = pd.DataFrame(features.tolist())
    predictions = xgb_model.predict(feature_df.values)
    return pd.Series(predictions, dtype=float)

# Apply UDF to Spark DataFrame
predictions_df = batch_data.withColumn(
    "predicted_time_s",
    pred_udf(struct([col(f) for f in feature_columns]))
)
```

### Write Amplification Issue
> When writing predictions back to a lakehouse, avoid updating the feature table directly for each prediction — lakehouse is not efficient for small updates. Refactor labels to a **child feature group** with append-only writes.

---

## Online Inference Architecture

### Deployment API vs. Model Signature

```
Deployment API (stable, public):          Model Signature (internal, flexible):
  serving_keys      → feature store lookup    numpy array / DataFrame
  passed_features   → ODTs already computed   → prediction (float)
  request_params    → for ODT computation
  prediction        ← response
```

**Rule:** The deployment API should NEVER change unexpectedly — it's a contract with clients. The model signature can change across model versions as long as the feature pipeline and deployment API adapt.

### Three Input Categories at Inference Time

```python
class Predictor:
    def load(self):
        self.fv = fs.get_feature_view("time_estimator_fv", version=1)
        self.model = mlflow.pyfunc.load_model(model_uri)

    def predict(self, inputs: dict):
        features = self.fv.get_feature_vector(
            serving_keys={                      # → lookup precomputed features from online store
                "athlete_id": inputs["athlete_id"],
            },
            passed_features={                   # → features computed by the client / API caller
                "current_hr": inputs["current_hr"],
                "current_pace": inputs["current_pace"],
            },
            request_parameters={                # → parameters for ODT computation in serving code
                "ts": inputs["timestamp"],
            }
        )
        prediction = self.model.predict(features)

        # Async non-blocking logging (don't block the response)
        self.fv.log_features_and_predictions(features, prediction, inputs["timestamp"])

        return {"predicted_time_s": prediction[0]}
```

### Failure Handling in Online Inference
```python
def get_features_with_fallback(athlete_id: str) -> dict:
    try:
        return fv.get_feature_vector(serving_keys={"athlete_id": athlete_id})
    except TimeoutError:
        # Option 1: Return cached values from TTL cache
        return cache.get(f"features:{athlete_id}", default=DEFAULT_FEATURES)
    except FeatureNotFound:
        # Option 2: Fall back to simpler model that doesn't need online store
        return {"ctl_42d": 50, "acwr": 1.0}  # population median imputation
```

---

## FastAPI for Model Serving

```python
from fastapi import FastAPI
import mlflow

app = FastAPI()
model = mlflow.pyfunc.load_model(model_uri)
fv = fs.get_feature_view("time_estimator_fv", version=1)

@app.post("/predict")
async def predict(request: PredictRequest):
    features = fv.get_feature_vector(
        serving_keys={"athlete_id": request.athlete_id},
        passed_features={"distance_km": request.distance_km}
    )
    prediction = model.predict(features)
    return {"predicted_time_s": float(prediction[0])}
```

---

## KServe: Enterprise Model Serving

```
KServe deployment architecture:
┌─────────────────────────────────────────────────────────┐
│                    KServe InferenceService               │
├────────────────────────────┬────────────────────────────┤
│     Transformer Container  │     Predictor Container    │
│  (FastAPI-based)           │  (pluggable backend)       │
│  - Feature store lookup    │  - Triton (ONNX, TF, PyTorch)│
│  - Preprocessing (ODTs)    │  - vLLM (LLMs)             │
│  - Postprocessing          │  - TorchServe              │
│  - Logging                 │  - ONNX Runtime            │
└────────────────────────────┴────────────────────────────┘

Capabilities:
  - A/B testing: canary weight configuration
  - Serverless autoscaling: KEDA + Prometheus (token throughput)
  - Multi-model serving on same GPU
  - Blue/green deployments
```

---

## Mixed-Mode UDFs: Same Function, Different Runtimes

The book recommends writing the same prediction function to work in both online and batch:

```python
def predict_features(features):
    """Works as Python (online) or Pandas UDF (batch) via dynamic typing."""
    if isinstance(features, dict):
        # Online mode: single prediction
        return model.predict([list(features.values())])[0]
    elif isinstance(features, pd.DataFrame):
        # Batch mode: batch prediction
        return model.predict(features.values)

# Online inference (Python UDF — low latency):
result = predict_features({"ctl_42d": 75, "acwr": 1.1, ...})

# Batch inference (Pandas UDF — high throughput):
@pandas_udf(FloatType())
def batch_predict(features: pd.Series) -> pd.Series:
    return pd.Series(predict_features(pd.DataFrame(features.tolist())))
```

---

## Streaming Inference Pipeline

```python
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import FloatType

@pandas_udf(FloatType())
def predict_stream(features: pd.Series) -> pd.Series:
    model = load_model(broadcasted_model_path.value)
    return pd.Series(model.predict(pd.DataFrame(features.tolist())))

# Spark Structured Streaming
stream_df = spark.readStream.format("kafka") \
    .option("subscribe", "athlete_events") \
    .load()

predictions = stream_df.withColumn("prediction", predict_stream(...))

# Write predictions back to feature store (append only)
fg.insert_stream(predictions, queryName="athlete_streaming_predictions")
```

---

## Embedded Models (Edge / High-Performance)

```python
# Embedded model: loaded from local disk, no network calls, sub-millisecond inference
import joblib
import os

class EmbeddedPredictor:
    def __init__(self, model_path: str):
        # Load from local disk at startup — not from registry at each call
        self.model = joblib.load(model_path)

    def predict(self, features: dict) -> float:
        X = np.array([[features[f] for f in FEATURE_ORDER]])
        return float(self.model.predict(X)[0])

# Use cases:
# - Mobile apps (on-device inference)
# - Edge devices (GPS watches, IoT)
# - Ultra-low latency APIs (<1ms)
# - Air-gapped environments
```

---

## UI for Inference Results

The book recommends Streamlit or Gradio for quick dashboards:

```python
import streamlit as st

st.title("Athlete Race Time Predictor")

athlete_id = st.selectbox("Select athlete", athlete_list)
distance = st.selectbox("Race distance", ["5K", "10K", "21K", "42K"])

if st.button("Predict"):
    features = fv.get_feature_vector(serving_keys={"athlete_id": athlete_id})
    prediction = model.predict(features)
    st.metric("Predicted Time", format_time(prediction[0]))
    st.bar_chart(shap_values_for_athlete(features))
```

---

## ODT / MDT Consistency: Prevent Skew

**Critical rule from the book:** ODTs and MDTs must use the **exact same function code** in both training pipeline and inference pipeline:

```python
# shared_transforms.py — imported by BOTH training and inference
def normalize_ctl(ctl_42d: float, ctl_mean: float, ctl_std: float) -> float:
    """MDT: model-specific normalization. Must be identical in training and inference."""
    return (ctl_42d - ctl_mean) / ctl_std

def compute_pace_deviation(current_pace: float, historical_avg: float) -> float:
    """ODT: request-time computation. Used in feature pipeline (batch) and serving code."""
    return (current_pace - historical_avg) / historical_avg
```

---

## Athlete Platform Inference Pipeline

```python
# src/notebooks/Batch_Inference.py structure:

# 1. Load model from registry
model = mlflow.pyfunc.load_model("models:/uc_athlete_data.models.time_estimator/latest")

# 2. Get features for all athletes (yesterday's data)
batch_data = feature_view.get_batch_data(start_time=yesterday, end_time=today)

# 3. Apply MDTs (same code as training pipeline)
X = apply_mdt_transforms(batch_data[feature_cols])

# 4. Predict
predictions = model.predict(X)

# 5. Write to Gold table
write_predictions_to_gold(batch_data["athlete_id"], predictions)
```
