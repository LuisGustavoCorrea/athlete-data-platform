# Governance, Lineage, and Versioning for ML Systems

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 13)

## Why Governance Matters

The book frames governance around three regulatory drivers:
- **EU AI Act**: risk classification, conformity assessment, intended use documentation
- **GDPR**: PII tracking, right to erasure, data minimization
- **Internal compliance**: audit trails, access control, data contracts

> "Governance is not bureaucracy — it is the metadata layer that enables debugging, compliance, and trust in ML systems."

---

## Lineage Graph

The book defines the complete **provenance chain** for any ML prediction:

```
Data Source
    │
    ▼
Feature Group (version)
    │
    ▼
Feature View (version)
    │
    ▼
Training Dataset (version + commit_ids)
    │
    ▼
Model (version + training_dataset_version)
    │
    ▼
Deployment (version + model_version)
    │
    ▼
Prediction (logged with all upstream metadata)
```

This chain enables: "Which raw data contributed to this prediction?" — answered in seconds, not days.

---

## Schematized Tags (from the book)

Feature stores support **schematized tags** — structured metadata attached to feature groups and feature views for compliance:

### EU AI Act Tag
```python
fg.add_tag(
    name="eu_ai_act",
    value={
        "risk_level": "limited",                     # minimal/limited/high/unacceptable
        "conformity_passed_date": "2024-06-01",
        "intended_use": "Athletic performance prediction for recreational runners",
        "prohibited_use": "Medical diagnosis, insurance underwriting",
        "human_oversight": True,
        "version": "1.0"
    }
)
```

### GDPR / PII Tag
```python
fg.add_tag(
    name="gdpr",
    value={
        "contains_pii": True,
        "pii_columns": ["athlete_id", "full_name", "email"],
        "data_subject_category": "health_data",        # special category
        "legal_basis": "explicit_consent",
        "retention_days": 365,
        "erasure_supported": True
    }
)
```

### Data Quality / SLO Tag
```python
fg.add_tag(
    name="data_contract",
    value={
        "owner": "data-engineering-team",
        "freshness_slo_hours": 24,
        "expected_row_count_min": 100,
        "expected_null_rate_max": 0.05,
        "schema_version": "1.2.0"
    }
)
```

---

## Versioning Strategy

### What Gets Versioned

| Artifact | Versioning Approach | When to Bump Version |
|---------|-------------------|---------------------|
| **Feature Groups** | Integer version number | Schema change (new/removed column), type change |
| **Feature Views** | Integer version number | Feature set changes, label changes |
| **Training Datasets** | `training_dataset_version` stored in model | Any time training data changes |
| **Models** | MLflow registered model versions | Any retrain |
| **Pipelines** | Git commit SHA | Any code change |
| **Deployments** | Deployment version | Any model version change |

### Schema-Breaking Changes

```
NON-BREAKING (no version bump needed):
  ✓ Adding a new feature column (backwards compatible)
  ✓ Changing a description or tag
  ✓ Updating default values

BREAKING (new version required):
  ✗ Removing a feature column
  ✗ Changing a column type (float → int)
  ✗ Renaming a primary key
  ✗ Changing event_time column
```

```python
# Schema-breaking change: create new version
fg_v2 = fs.get_or_create_feature_group(
    name="athlete_rolling_features",
    version=2,   # ← bump version
    primary_key=["athlete_id"],
    event_time="as_of_date",
    description="Added pace_variability feature, removed deprecated avg_speed"
)
```

---

## Audit Logs

Feature stores generate audit logs for:

```
READ events:
  - Who read which feature group (user, timestamp, query)
  - Which training dataset was created from which feature view
  - Which deployment reads which online feature group

WRITE events:
  - Who inserted data into which feature group (pipeline, timestamp, row_count)
  - Data validation results (pass/fail, expectations summary)

ACCESS CONTROL events:
  - Permission grants/revocations
  - Cross-team feature access requests
```

---

## Feature Discovery and Collaboration

```python
# Search feature catalog
features = fs.search_feature_groups(query="training load")
# → Returns: athlete_rolling_features, activity_features, ...

# Get feature statistics
fg.get_feature_group_statistics()
# → min, max, mean, std, null_rate per column, computed on last insert

# Feature group description (used for LLM-assisted feature selection)
fg = fs.get_feature_group("athlete_rolling_features", version=1)
print(fg.description)
# → "Rolling aggregations of training load metrics per athlete:
#    CTL (42-day EMA of TSS), ATL (7-day EMA), ACWR, pace trend"
```

---

## Reproducibility: Pinning Training Data

```python
# At training time: store all identifiers needed to reproduce training data
with mlflow.start_run():
    mlflow.log_params({
        # Feature provenance
        "feature_view_name": "time_estimator_fv",
        "feature_view_version": 1,
        "feature_group_versions": {
            "athlete_rolling_features": 1,
            "activity_features": 2,
        },
        # Training data snapshot
        "training_dataset_version": td.version,
        "training_dataset_commit_id": td.commit_id,
        # Reproducibility
        "random_seed": 42,
        "train_start": "2022-01-01",
        "train_end": "2024-06-01",
        "test_start": "2024-07-16",  # gap for rolling features
    })
    mlflow.sklearn.log_model(model, "model")

# → Months later, reproduce exact training data:
td = feature_view.get_training_dataset(version=td_version)
X, y = td.read()  # exact same data
```

---

## In Databricks with Unity Catalog

```
Unity Catalog governance layers:
  - Catalog-level:  uc_athlete_data (ownership, access control)
  - Schema-level:   feature_store, gold, models (team permissions)
  - Table-level:    athlete_rolling_features (column-level masking, row filtering)
  - Column-level:   PII masking for athlete_id, name

Lineage UI: Unity Catalog → Data → Lineage tab
  → Visual graph of: source tables → feature tables → models → downstream tables

Audit logs: Unity Catalog → Governance → Audit Logs
  → SQL-queryable log of all read/write operations
```

---

## Compliance Checklist

```
DATA GOVERNANCE
[ ] All feature groups have owner tag
[ ] PII columns identified and tagged
[ ] Retention policy set for sensitive data
[ ] Access control: right teams have read access

LINEAGE
[ ] Feature group → feature view → training dataset linkage established
[ ] Model registered with feature_view reference
[ ] training_dataset_version stored in model metadata

VERSIONING
[ ] Schema-breaking changes create new feature group version
[ ] Old versions kept for rollback (don't delete!)
[ ] Changelog maintained in feature group description

AUDIT
[ ] Data validation results logged per pipeline run
[ ] Model evaluation results logged (metrics + bias tests)
[ ] Deployment events logged (who deployed what when)
```
