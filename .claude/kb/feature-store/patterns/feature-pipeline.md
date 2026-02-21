# Pattern: Feature Pipeline

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 2, 8)

## Definition

A Feature Pipeline is a program that:
- **Input**: raw data (files, streams, databases)
- **Output**: features written to the Feature Store (MITs only)
- **Contract**: idempotent, versioned, testable, parameterized by time range

---

## Structure (from the book, Ch. 8)

```python
# Standard Batch Feature Pipeline — parameterized by time range
import os

START_TIME = os.environ.get("START_TIME", yesterday())
END_TIME   = os.environ.get("END_TIME",   today())

# 1. READ — ingest raw/silver data for the time window
raw_df = spark.table("catalog.silver.strava_activities") \
    .filter(col("start_date").between(START_TIME, END_TIME))

# 2. VALIDATE — check data quality (Great Expectations / assertions)
assert raw_df.count() > 0, "No data for time window"
assert raw_df.filter(col("distance_km") <= 0).count() == 0

# 3. TRANSFORM — compute MIT features (no MDTs here)
features_df = (raw_df
    .withColumn("pace_min_km", col("elapsed_time_s") / 60 / col("distance_km"))
    .withColumn("elevation_per_km", col("elevation_gain") / col("distance_km"))
    .withColumn("estimated_tss", calculate_tss_udf(col("pace_min_km"), col("elapsed_time_s")))
)

# 4. WRITE — store in Feature Store (idempotent upsert)
fg.insert(features_df, write_options={"wait_for_job": True})
```

---

## Data Sources (from Ch. 8)

### Batch Sources
| Type | Examples | Access Pattern |
|------|---------|----------------|
| **Columnar stores** | Delta Lake, Iceberg, Parquet | Time-range query |
| **Row-oriented stores** | MySQL, PostgreSQL | Polling or CDC |
| **Object stores** | S3, ADLS, GCS | File listing + read |
| **NoSQL** | MongoDB, DynamoDB | Document scan |
| **SaaS APIs** | Strava, Garmin, Fitbit | REST API polling |

### Streaming Sources
| Type | Examples | Use Case |
|------|---------|---------|
| **Message queues** | Kafka, Kinesis | Real-time events |
| **Change streams** | DynamoDB Streams | CDC from databases |
| **IoT** | MQTT brokers | Sensor data |

### Synthetic Data with LLMs
> "Use LLMs to generate realistic synthetic data for bootstrapping feature pipelines before real data is available." — Ch. 8

---

## Backfill vs. Incremental: Same Program

The book recommends a **single program** parameterized by `START_TIME` / `END_TIME`:

```python
# BACKFILL: run for full history
START_TIME=2022-01-01 END_TIME=2024-01-01 python feature_pipeline.py

# INCREMENTAL: run for yesterday
START_TIME=2024-06-14 END_TIME=2024-06-15 python feature_pipeline.py

# Same code, different time windows — no duplication
```

---

## Polling vs. CDC (Change Data Capture)

| Approach | How | Pros | Cons |
|---------|-----|------|------|
| **Polling** | Query for records since last run | Simple to implement | Misses deletions, "ghost rows" (late arrivals can be missed) |
| **CDC** | Capture all change events (insert/update/delete) | Captures all changes including deletions | More complex setup |

> **Recommendation (book):** Prefer CDC when source database supports it. Polling can miss ghost rows — rows deleted after they were polled.

```python
# CDC example: Debezium → Kafka → Feature Pipeline
# Each event: {"op": "c"/"u"/"d", "before": {...}, "after": {...}, "ts_ms": ...}

def process_cdc_event(event):
    if event["op"] in ["c", "u"]:  # create or update
        fg.insert(pd.DataFrame([event["after"]]))
    elif event["op"] == "d":        # delete
        fg.delete(event["before"]["primary_key"])
```

---

## Orchestrators

| Orchestrator | When to Use | Key Feature |
|-------------|------------|-------------|
| **Modal** | Serverless, auto-containerization | Per-function containers, GPU support |
| **Hopsworks Jobs** | Hopsworks platform | Reusable environments, no Docker required |
| **Apache Airflow** | Complex DAGs, on-prem | DAG-based, mature ecosystem |
| **Azure ADF** | Azure ecosystem | Visual pipelines, connectors |
| **AWS Step Functions** | AWS ecosystem | Serverless state machine |
| **Databricks Workflows** | Databricks platform | DABs integration, cluster reuse |

### Modal Example (Auto-containerization)
```python
import modal

image = modal.Image.debian_slim().pip_install(["hopsworks", "pandas"])
secret = modal.Secret.from_name("hopsworks-api-key")
app = modal.App("athlete-feature-pipeline")

@app.function(
    schedule=modal.Period(days=1),
    image=image,
    cpu=4.0,
    memory=8192,
    secrets=[secret]
)
def daily_feature_job():
    import hopsworks
    fs = hopsworks.login().get_feature_store()
    fg = fs.get_feature_group("athlete_rolling_features", version=1)
    features_df = compute_features(start_time=yesterday(), end_time=today())
    fg.insert(features_df)
```

### Databricks Workflows Example (DABs)
```yaml
# resources/feature-store-pipeline.yml
resources:
  jobs:
    feature_store_pipeline:
      name: feature-store-pipeline
      tasks:
        - task_key: feature_activity
          notebook_task:
            notebook_path: src/notebooks/Feature_Activity.py
        - task_key: feature_rolling
          depends_on: [feature_activity]
          notebook_task:
            notebook_path: src/notebooks/Feature_Rolling.py
      schedule:
        quartz_cron_expression: "0 0 6 * * ?"  # 6am daily
```

---

## Data Contracts (from Ch. 8)

A data contract defines:
1. **Schema validation**: expected columns, types
2. **SLO guarantees**: freshness, row count, null rates
3. **Governance tags**: PII, sensitivity, compliance

```python
# Great Expectations attached to feature group
from great_expectations.core import ExpectationSuite

suite = ExpectationSuite(
    expectation_suite_name="athlete_features_contract",
    expectations=[
        ExpectColumnValuesToBeBetween("pace_min_km", min_value=2.0, max_value=20.0),
        ExpectColumnValuesToNotBeNull("athlete_id"),
        ExpectColumnValuesToNotBeNull("distance_km"),
        ExpectTableRowCountToBeGreaterThan(0),
    ],
    meta={"ingestion_policy": "STRICT"}  # reject all rows on failure
)
fg.save_expectation_suite(expectation_suite=suite)
```

### STRICT vs. ALWAYS Ingestion Policy
| Policy | Behavior on Validation Failure |
|--------|-------------------------------|
| `STRICT` | Reject the entire insert — no bad data enters the store |
| `ALWAYS` | Insert anyway — useful for logging/debugging but risky for production |

---

## WAP Pattern: Write-Audit-Publish

The book recommends WAP for production feature pipelines (maps to Medallion Architecture):

```
BRONZE (Write)  →  SILVER (Audit)  →  GOLD/FEATURE STORE (Publish)
  Raw data           Cleaned              MIT features
  No transforms      Validated            Ready for ML
  Append only        Schema checked       Merge/upsert
```

```python
# WAP Implementation
# 1. WRITE to bronze (raw, no validation)
raw_df.write.mode("append").saveAsTable("catalog.bronze.strava_activities")

# 2. AUDIT silver (validate, transform to MITs)
silver_df = bronze_df.transform(validate_and_clean)
silver_df.write.mode("merge").saveAsTable("catalog.silver.strava_activities")

# 3. PUBLISH to feature store (only if validation passes)
if validation_passed:
    features_df = silver_df.transform(compute_mit_features)
    fg.insert(features_df)
```

---

## Idempotency (Critical)

Feature pipelines MUST be idempotent — running twice for the same time window produces the same result:

```python
# WRONG: appends on every run → duplicates
df.write.mode("append").saveAsTable("feature_store.activity_features")

# CORRECT: merge upserts based on primary key + event_time
fg.insert(df)  # feature store handles upsert semantics

# OR in Databricks:
fe.write_table(
    name="catalog.feature_store.activity_features",
    df=df,
    mode="merge"   # ← upsert by primary_key + timestamp_key
)
```

---

## Transformation Taxonomy

| Type | Book Term | When Computed | Example |
|------|-----------|---------------|---------|
| **Model-Independent** | MIT | Feature Pipeline (once) | CTL, ACWR, windowed pace |
| **Model-Dependent** | MDT | Training + Inference | Normalization, one-hot encoding |
| **On-Demand** | ODT | Inference + batch logging | current_hr/threshold_hr |
| **Stateless** | (subset of MIT) | Row-by-row | `pace = distance / time` |
| **Stateful (windowed)** | (subset of MIT) | Requires history | `CTL = rolling_avg(tss, 42d)` |

---

## Athlete Platform Pipeline DAG

```
bronze.strava_activities
      │
      ▼
silver.strava_activities ──── silver.strava_sub_activity
      │                              │
      └──────────────┬───────────────┘
                     ▼
            Feature_Activity.py         (MITs: pace, elevation, TSS, HR features)
            → feature_store.activity_features
                     │
                     ▼
            Feature_Rolling.py          (MITs: CTL, ATL, ACWR, 30d/90d rolling)
            → feature_store.athlete_rolling_features
```
