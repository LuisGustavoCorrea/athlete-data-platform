# Pattern: Training Pipeline

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 10)

## Definition

A Training Pipeline is a program that:
- **Input**: feature view (features + labels) from feature store
- **Output**: trained model registered in model registry
- **Contract**: reproducible, gated (performance threshold), linked to feature version

---

## Labels in Feature Groups

The book is clear: **labels are stored in feature groups** like any other feature:

```python
# Labels stored as a feature group (SCD Type 2)
labels_fg = fs.get_or_create_feature_group(
    name="race_results",
    version=1,
    primary_key=["athlete_id", "race_id"],
    event_time="race_date",
)
labels_fg.insert(race_results_df)

# Feature view designates the label column
feature_view = fs.get_or_create_feature_view(
    name="time_estimator_fv",
    version=1,
    query=rolling_fg.select(["ctl_42d", "acwr", "pace_trend_30d"])
          .join(labels_fg.select(["target_time_seconds"], label=True))
)
```

**Supported learning types:**
- Supervised: label in feature group, designated in feature view
- Unsupervised: no label designation (clustering, anomaly detection)
- Self-supervised: model generates its own labels (time-series forecasting next step)

---

## Feature Selection Methods

| Method | Approach | When to Use |
|--------|---------|------------|
| **Filter** | Mutual information, correlation | Quick first pass, remove irrelevant |
| **Wrapper** | Recursive Feature Elimination (RFE) | Iterative, model-informed |
| **Embedded** | L1/L2 regularization in model | When using linear models |
| **LLM-assisted** | RAG over feature group descriptions | When feature catalog is large |

### LLM-Assisted Feature Selection
```python
# Use LLM to suggest features from feature catalog
# RAG: retrieve relevant feature group descriptions → LLM picks top candidates
system_prompt = """
You are a feature selection expert. Given the prediction task and feature catalog,
suggest the most likely useful features. Explain your reasoning.

Prediction task: Predict 10K race time for a runner
Feature catalog:
{feature_catalog_descriptions}

Suggest top 10 features and why.
"""
```

---

## Training Data Formats

| Format | Use Case | Library |
|--------|---------|---------|
| **Pandas DataFrame** | Small datasets (<1M rows) | scikit-learn, XGBoost |
| **Polars DataFrame** | Medium datasets | faster Pandas alternative |
| **CSV / Parquet files** | Scikit-learn, XGBoost batch | Standard ML |
| **JSONL files** | LLM fine-tuning | OpenAI, Hugging Face |
| **TFRecord** | TensorFlow / PyTorch streaming | Large-scale deep learning |
| **HDF5 / NPY** | Tensor data | NumPy, PyTorch |

```python
# Retrieve training data from feature view
X_train, X_test, y_train, y_test = feature_view.train_test_split(
    test_size=0.2,
    description="Time estimator training data v1"
)
# → creates a training_dataset versioned in the feature store
```

---

## Splitting Strategies

| Strategy | Use Case | Code |
|---------|---------|------|
| **Random split** | i.i.d. data | `train_test_split(random_state=42)` |
| **Time-series split** | Sequential dependencies | Sort by time, no random shuffle |
| **Group split** | Athletes in same group stay together | `GroupShuffleSplit(groups=athlete_id)` |

### Time-Series Split with Gap
```python
# For rolling features (CTL = 42d EMA), add gap to prevent leakage
train = df[df["race_date"] < "2024-06-01"]
# gap: 2024-06-01 to 2024-07-15 (43+ days for 42d rolling window)
test  = df[df["race_date"] >= "2024-07-16"]

# Also useful: sklearn's TimeSeriesSplit for cross-validation
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5, gap=43)
```

---

## Model Architecture Selection Rule (from the book)

> **Rule of thumb:**
> - **< 10M rows → XGBoost / decision trees** (almost always wins)
> - **10M–100M rows → either** (benchmark both)
> - **> 100M rows → Neural Networks**

```python
# XGBoost: best for tabular data < 10M rows
import xgboost as xgb
model = xgb.XGBClassifier(
    objective="binary:logistic",
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    use_label_encoder=False,
    eval_metric="logloss"
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=20)
```

---

## Hyperparameter Tuning: Ray Tune + ASHA + Optuna

```python
import ray
from ray import tune
from ray.tune.schedulers import ASHAScheduler
from ray.tune.search.optuna import OptunaSearch

param_space = {
    "max_depth": tune.randint(3, 10),
    "learning_rate": tune.loguniform(0.01, 0.3),
    "n_estimators": tune.randint(100, 500),
    "subsample": tune.uniform(0.6, 1.0),
}

def train_xgboost(config):
    model = xgb.XGBClassifier(**config)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=20)
    preds = model.predict(X_val)
    tune.report({"f1_score": f1_score(y_val, preds)})

tuner = tune.Tuner(
    train_xgboost,
    param_space=param_space,
    tune_config=tune.TuneConfig(
        scheduler=ASHAScheduler(metric="f1_score", mode="max"),
        search_alg=OptunaSearch(metric="f1_score", mode="max"),
        num_samples=50,
    )
)
results = tuner.fit()
best_config = results.get_best_result().config
```

---

## Reproducible Training Data

The book emphasizes tracking exactly which data was used to train each model:

```python
# What to store in model registry for reproducibility:
mlflow.log_params({
    "training_dataset_version": feature_view.get_latest_training_dataset().version,
    "feature_group_version": fg.version,
    "random_seed": RANDOM_SEED,
    "train_start": TRAIN_START,
    "train_end": TRAIN_END,
    "test_start": TEST_START,
})
# → Enables exact reproduction of training data months later
```

---

## Model Evaluation: Performance + Bias

```python
from sklearn.metrics import f1_score, roc_auc_score, confusion_matrix
import shap

# Standard evaluation
metrics = {
    "mae_minutes": mean_absolute_error(y_test, preds) / 60,
    "f1": f1_score(y_test, preds_class),
    "roc_auc": roc_auc_score(y_test, preds_proba),
}

# SHAP: interpretability
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test)  # → feature importance

# Bias test: evaluate on population slices
# training_helper_columns: columns used for bias testing but NOT as model features
for activity_type in ["run", "ride", "swim"]:
    slice_df = test_df[test_df["activity_type"] == activity_type]
    slice_mae = mean_absolute_error(slice_df["y_true"], model.predict(slice_df[feature_cols])) / 60
    assert slice_mae < MAX_SLICE_MAE, f"Bias detected for {activity_type}: MAE={slice_mae:.1f}min"

# Performance gate: only register if all checks pass
if metrics["mae_minutes"] < 3.0 and all_bias_tests_pass:
    mlflow.register_model(model_uri, "uc_athlete_data.models.time_estimator")
```

---

## Distributed Training (for large-scale models)

| Strategy | Framework | Use Case |
|---------|----------|---------|
| **Data-parallel** | Ray Train + ring all-reduce | Same model, different data shards |
| **Tensor parallelism** | Megatron-LM | Very large matrices (>100B params) |
| **Model-parallel** | DeepSpeed ZeRO-3 | Model doesn't fit on one GPU |

### LoRA / QLoRA for LLM Fine-Tuning
```python
from peft import LoraConfig, get_peft_model

# LoRA: freeze base weights, train only low-rank adapter matrices
# → 95% fewer trainable parameters than full fine-tuning
config = LoraConfig(
    r=16,               # rank of adapter matrices
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.1
)
model = get_peft_model(base_model, config)
```

---

## Model File Formats

| Format | Use Case | Library |
|--------|---------|---------|
| `.safetensors` | HuggingFace models (safe, fast) | `safetensors` |
| `.pkl` / joblib | scikit-learn models | `joblib` |
| `.json` + `.ubj` | XGBoost native format | `xgb.save_model()` |
| `.onnx` | Cross-platform inference | ONNX Runtime |
| `.pt` / `.pth` | PyTorch models | `torch.save()` |
| `.engine` | TensorRT (GPU-optimized) | NVIDIA TensorRT |

---

## Model Cards

The book recommends publishing a one-page **Model Card** for every registered model:

```markdown
# Model Card: Time Estimator v2

## Intended Use
Predict finish time for 5k/10k/21k/42k races given current training load metrics.

## Model Details
- Architecture: XGBoost (max_depth=6, n_estimators=300)
- Training data: athlete_rolling_features v3 (2022-01-01 to 2024-06-01)
- Features: ctl_42d, atl_7d, acwr, pace_trend_30d, consistency_score

## Evaluation Results
- MAE: 2.3 minutes (10K), 4.1 minutes (42K)
- ROC AUC: 0.87 (sub/supra threshold classifier)

## Bias Tests
- Activity type slices: run (MAE=2.1), ride (MAE=2.8), swim (N/A)
- Gender: male (MAE=2.2), female (MAE=2.4) — acceptable

## Deployment Instructions
- Batch inference: read from athlete_rolling_features, write to gold.predictions
- Online inference: use feature_view.get_feature_vector(athlete_id)
```

---

## Athlete Platform Training Pipeline

```python
# src/notebooks/Train_Time_Estimator.py structure:

# 1. Get training data from feature view (point-in-time correct)
X_train, X_test, y_train, y_test = feature_view.train_test_split(test_size=0.2)

# 2. Select features (filter by correlation + SHAP)
selected_features = ["ctl_42d", "atl_7d", "acwr", "pace_trend_30d", "elevation_per_km"]

# 3. Train with hyperparameter tuning
best_model = tune_xgboost(X_train[selected_features], y_train)

# 4. Evaluate + bias tests
evaluate_and_gate(best_model, X_test, y_test, threshold_mae=3.0)

# 5. Register model with lineage
fe.log_model(best_model, training_set=training_set,
             registered_model_name="uc_athlete_data.models.time_estimator")
```
