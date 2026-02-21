# Pattern: Point-in-Time Joins

> Source: "Building ML Systems with a Feature Store" — Jim Dowling, O'Reilly (Ch. 4)

## Problem: Data Leakage in Training

Without point-in-time joins, training data uses **future feature values** — values that wouldn't be available at prediction time. This inflates model metrics and leads to production underperformance.

```
Label event at T=100 (athlete ran 10K in 45min)

❌ WRONG: features joined at query time (T=today)
   → uses CTL=85 (today's fitness) to predict T=100 race
   → CTL was 72 at T=100 → DATA LEAKAGE

✅ CORRECT: features joined at event time (T=100)
   → uses CTL=72 (fitness at race day)
   → no leakage → honest evaluation
```

---

## ASOF LEFT JOIN: The Mechanism

The book shows the exact SQL that feature stores use for point-in-time joins:

```sql
-- ASOF LEFT JOIN: starts from labels, pulls feature values WHERE feature.event_ts <= label.event_ts
SELECT
    label.target_time_seconds,
    rolling.ctl_42d,
    rolling.acwr,
    rolling.pace_trend_30d,
    activity.pace_min_km,
    activity.elevation_per_km,
    profile.country
FROM athlete_labels_fg AS label
ASOF LEFT JOIN athlete_rolling_fg AS rolling
    ON label.athlete_id = rolling.athlete_id
    AND rolling.as_of_date <= label.race_date    -- ← no future values
ASOF LEFT JOIN activity_fg AS activity
    ON label.athlete_id = activity.athlete_id
    AND activity.event_time <= label.race_date
ASOF LEFT JOIN athlete_profile_fg AS profile
    ON label.athlete_id = profile.athlete_id
WHERE label.race_date > '2023-01-01 00:00';
```

**Rule:** The ASOF JOIN finds the **most recent** feature value before or at the label's timestamp. No future data leaks in.

---

## Feature Group Requirements for Point-in-Time

Feature groups must have an `event_time` column to support point-in-time joins:

```python
# Hopsworks example
fg = fs.get_or_create_feature_group(
    name="athlete_rolling_features",
    version=1,
    primary_key=["athlete_id"],
    event_time="as_of_date",      # ← required for point-in-time
    online_enabled=False,          # SCD Type 2 (offline only, batch ML)
)

# Databricks Feature Engineering example
fe.create_table(
    name="uc_athlete_data.feature_store.athlete_rolling_features",
    primary_keys=["athlete_id"],
    timestamp_keys=["as_of_date"],   # ← enables point-in-time
    df=rolling_features_df,
    description="Rolling training load metrics per athlete per day"
)
```

---

## Training Set with Point-in-Time Lookup

### Databricks Feature Engineering API
```python
from databricks.feature_engineering import FeatureLookup

# Step 1: Label DataFrame — entity key + label + event timestamp
labels_df = spark.createDataFrame([
    ("athlete_001", "2024-06-15", 2700),   # 10K in 45min on June 15
    ("athlete_001", "2024-09-20", 2580),   # 10K in 43min on Sept 20
    ("athlete_002", "2024-07-04", 3120),   # 10K in 52min on July 4
], ["athlete_id", "race_date", "actual_time_seconds"])

# Step 2: Create training set with point-in-time feature lookup
training_set = fe.create_training_set(
    df=labels_df,
    feature_lookups=[
        FeatureLookup(
            table_name="uc_athlete_data.feature_store.athlete_rolling_features",
            lookup_key=["athlete_id"],
            timestamp_lookup_key="race_date",    # ← point-in-time: features AS OF race_date
            feature_names=["ctl_42d", "atl_7d", "acwr", "pace_trend_30d"]
        ),
        FeatureLookup(
            table_name="uc_athlete_data.feature_store.activity_features",
            lookup_key=["athlete_id"],
            timestamp_lookup_key="race_date",
            feature_names=["elevation_per_km", "hr_zone_distribution"]
        )
    ],
    label="actual_time_seconds"
)

training_df = training_set.load_df()
# → returns features that existed on race_date, not today's features
```

---

## Labels in Feature Groups

The book is explicit: **labels are stored in feature groups**. They are only *designated* as labels in feature views.

```python
# Labels stored as a regular feature group
labels_fg = fs.get_or_create_feature_group(
    name="race_results",
    version=1,
    primary_key=["athlete_id", "race_id"],
    event_time="race_date",
)
labels_fg.insert(race_results_df)

# Feature view designates which column is the label
feature_view = fs.get_or_create_feature_view(
    name="time_estimator_fv",
    version=1,
    query=rolling_fg.select(["ctl_42d", "acwr"])
          .join(labels_fg.select(["target_time_seconds"], label=True))  # ← label designation
)
```

---

## Temporal Join Rules (from the book)

| Rule | Why |
|------|-----|
| Feature event_time ≤ label event_time | No future leakage |
| Use most recent feature value before label | ASOF semantics |
| Gap required for rolling aggregation features | e.g., ctl_42d needs 42d of history — add buffer |
| Same join logic in training and inference | Prevents skew |

### Time-Series Split Gap
When features include rolling windows, add a gap between train_end and test_start:
```python
# CTL is a 42-day exponential moving average
# → need gap between train_end and test_start to avoid leakage
train_end   = "2024-06-01"
gap_start   = "2024-06-02"
gap_end     = "2024-07-15"  # 43+ days gap for 42-day window
test_start  = "2024-07-16"
test_end    = "2024-12-31"
```

---

## Athlete Platform: Where This Matters

| Feature | Why Point-in-Time Critical |
|---------|---------------------------|
| `ctl_42d` | Fitness at race day, not current fitness |
| `pace_trend_30d` | Trend leading up to race, not recent trend |
| `acwr` | Training load ratio at time of race |
| `consistency_score` | Training regularity before race |

## Implementation Checklist

```
[ ] Feature groups have event_time (timestamp_keys) defined
[ ] Labels are in a feature group with event_time
[ ] FeatureLookup / feature_view uses timestamp_lookup_key
[ ] Verified: no future feature values in training data
[ ] Time-series split has appropriate gap for rolling features
[ ] Test: train on 2024 data, evaluate on held-out 2024 data (no leakage)
```
