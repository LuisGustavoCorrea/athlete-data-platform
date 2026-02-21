# Feature Store: Anatomy and Purpose

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 4)

## Brief History

| Year | Milestone |
|------|-----------|
| 2017 | Uber Michelangelo — first internal feature store |
| 2018 | Hopsworks — first open-source, API-based feature store |
| 2019 | Feast — open-source, cloud-native |
| 2020+ | GCP Vertex AI, AWS SageMaker, Databricks Feature Store |
| 2021+ | Tecton (DSL-based, enterprise), Hopsworks cloud |

---

## When to Use a Feature Store

| Situation | Use Feature Store? | Reason |
|-----------|-------------------|--------|
| Real-time context needed at inference | **Yes** | Online store enables <10ms feature lookup |
| Time-series features (CTL, ACWR) | **Yes** | Point-in-time joins prevent data leakage |
| Multiple teams sharing features | **Yes** | Collaboration + discovery |
| Compliance / audit requirements | **Yes** | Governance + lineage |
| Feature reuse across models | **Yes** | Compute once, use many |
| Training-serving skew problems | **Yes** | Same features, same code |
| Single model, batch only | Probably not | Added complexity without benefit |

---

## Anatomy: The Three Components

```
┌──────────────────────────────────────────────────────────────────┐
│                        FEATURE STORE                              │
├───────────────────────┬────────────────────┬─────────────────────┤
│     OFFLINE STORE     │    ONLINE STORE     │   VECTOR INDEX      │
│   (Training / Batch)  │  (Online Inference) │   (LLM / RAG)       │
├───────────────────────┼────────────────────┼─────────────────────┤
│ Columnar / Lakehouse  │ Row-oriented KV     │ Embedding store     │
│ Iceberg, Delta, Hudi  │ RonDB, DynamoDB,   │ Elasticsearch,      │
│ High throughput       │ Redis, Cassandra    │ Pinecone, PGVector  │
│ Historical data       │ Current values only │ ANN search          │
│ Point-in-time joins   │ <10ms lookup        │ Semantic similarity │
│ Used by training      │ Used by online API  │ Used by RAG agents  │
└───────────────────────┴────────────────────┴─────────────────────┘
```

---

## Feature Groups

A **Feature Group** is the fundamental unit of storage — a table with metadata:

```python
# Feature Group schema
fg = fs.get_or_create_feature_group(
    name="athlete_rolling_features",
    version=1,
    primary_key=["athlete_id"],      # entity key (who)
    event_time="as_of_date",         # temporal key (when)
    partition_key=["year", "month"], # storage partitioning
    online_enabled=True,             # sync to online store
    description="Rolling aggregations of training load metrics"
)
fg.insert(df)
```

### Feature Group Key Fields
| Field | Purpose | Example |
|-------|---------|---------|
| `primary_key` | Entity identifier(s) | `["athlete_id"]` |
| `event_time` | When the feature value was valid | `"as_of_date"` |
| `foreign_key` | Link to another feature group | `["activity_id"]` |
| `partition_key` | Storage partitioning for efficiency | `["year", "month"]` |
| `version` | Schema evolution tracking | `1`, `2`, `3`... |

### Rule: Feature Groups Store MITs Only
> Feature groups should contain **only Model-Independent Transformations (MITs)**.
> MDTs (normalization, encoding) are applied LATER in training/inference pipelines.

---

## SCD Types for Feature Groups

The book maps Slowly Changing Dimension types to feature store use cases:

| SCD Type | event_time | online_enabled | Use Case |
|---------|-----------|----------------|---------|
| **Type 0** | No event_time | Optional | Immutable reference data (athlete profile) |
| **Type 2** | Has event_time, offline only | False | Batch ML (historical training data) |
| **Type 4** | Has event_time, online + offline | True | Real-time ML (online inference + batch training) |

```
SCD Type 0 → static dimension (country, gender, DOB)
SCD Type 2 → offline history with snapshots → batch training
SCD Type 4 → synchronized online+offline → enables real-time inference
```

---

## Data Models: Star vs. Snowflake Schema

### Star Schema
- All features for an entity in **one wide table**
- Simpler queries, higher storage cost
- Works for: batch training only, simple models

```
         ┌──────────────────────────────┐
         │     activity_features_wide    │
         │  athlete_id (PK)             │
         │  activity_date (event_time)  │
         │  pace_min_km                 │
         │  distance_km                 │
         │  ctl_42d        ← all joined │
         │  acwr           ← into one   │
         │  athlete_country ← table     │
         └──────────────────────────────┘
```

### Snowflake Schema (Preferred)
- Features split across **multiple normalized feature groups**
- Lower storage, better for online+offline
- Works for: real-time + batch, online store efficiency

```
┌────────────────┐    ┌───────────────────────┐
│ athlete_profile│    │  activity_features     │
│ athlete_id (PK)│    │  athlete_id (FK)       │
│ country        │◄───│  activity_id (PK)      │
│ birth_year     │    │  event_time            │
└────────────────┘    │  pace_min_km           │
                      │  distance_km           │
                      └───────────┬────────────┘
                                  │
                      ┌───────────▼────────────┐
                      │  athlete_rolling_feats  │
                      │  athlete_id (FK)        │
                      │  as_of_date (event_time)│
                      │  ctl_42d                │
                      │  acwr                   │
                      └────────────────────────┘
```

---

## Feature Views

A **Feature View** is a **metadata-only** definition — it defines which features + labels a model uses, without duplicating data:

```python
feature_view = fs.get_or_create_feature_view(
    name="time_estimator_fv",
    version=1,
    query=rolling_fg.select(["ctl_42d", "acwr", "pace_trend_30d"])
          .join(activity_fg.select(["distance_km", "elevation_per_km"]))
          .join(labels_fg.select(["target_time_seconds"], label=True))
)
```

### What Feature Views Enable
1. **Point-in-time correct training data**: retrieves feature values AS OF the label timestamp
2. **Skew elimination**: same logic used for training data and online inference
3. **Feature discovery**: searchable catalog of model inputs
4. **Schema-breaking change protection**: new version required for incompatible changes

---

## ASOF LEFT JOIN: Point-in-Time Under the Hood

The book shows the SQL that feature stores execute for point-in-time joins:

```sql
-- Retrieve training data with no data leakage
SELECT
    label.target_time_seconds,
    rolling.ctl_42d,
    rolling.acwr,
    activity.pace_min_km,
    activity.distance_km,
    profile.country
FROM athlete_labels_fg AS label
ASOF LEFT JOIN athlete_rolling_fg AS rolling
    ON label.athlete_id = rolling.athlete_id
    AND rolling.as_of_date <= label.race_date   -- ← no future values
ASOF LEFT JOIN activity_fg AS activity
    ON label.athlete_id = activity.athlete_id
    AND activity.event_time <= label.race_date
ASOF LEFT JOIN athlete_profile_fg AS profile
    ON label.athlete_id = profile.athlete_id
WHERE label.race_date > '2023-01-01';
```

> **Key rule:** ASOF JOIN starts from the label table and pulls feature values where `feature.event_ts <= label.event_ts`. This guarantees no future leakage.

---

## Online Inference Feature Serving

```python
# At inference time (online, <10ms)
feature_vector = feature_view.get_feature_vector(
    entry=[{
        "athlete_id": "athlete_001",
        "activity_id": "act_20240615"
    }]
)
prediction = model.predict(feature_vector)
```

---

## In Databricks with Unity Catalog

```
Unity Catalog = Metadata Store + Governance
Delta Lake    = Offline Store
MLflow        = Model Registry (linked to features)
Feature Engineering APIs = Feature Groups + Views + Serving

uc_athlete_data
├── feature_store/        ← Offline store (Delta)
│   ├── activity_features          (SCD Type 2)
│   ├── athlete_weekly_features    (SCD Type 2)
│   └── athlete_rolling_features   (SCD Type 2 → future: Type 4)
└── models/               ← Model Registry
    └── time_estimator
```

## Lineage Tracking

Feature Store records the complete chain:
```
Data Source → Feature Group → Feature View → Training Data → Model → Deployment
```

This enables complete audit trail: prediction → model → features → raw data.
