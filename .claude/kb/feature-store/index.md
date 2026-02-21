# Knowledge Base: Feature Store & ML Systems

> Based on: "Building Machine Learning Systems with a Feature Store" — Jim Dowling, O'Reilly Media
> Source: [O'Reilly](https://www.oreilly.com/library/view/building-machine-learning/9781098165222/) | [GitHub](https://github.com/featurestorebook/mlfs-book)
> Content sourced from: Ch. 2, 4, 8, 10, 11, 13, 14 (PDF extracted, actual book content)

## What This KB Covers

Patterns and concepts for building production ML systems using the FTI (Feature/Training/Inference) pipeline architecture with a Feature Store as the central data layer.

## Concepts

| Concept | Description | File |
|---------|-------------|------|
| **FTI Architecture** | MVPS, Feature/Training/Inference pipelines, MIT/MDT/ODT taxonomy | [fti-architecture.md](concepts/fti-architecture.md) |
| **Feature Store** | History, anatomy, SCD types, star/snowflake schema, feature views | [feature-store-anatomy.md](concepts/feature-store-anatomy.md) |
| **ML System Types** | Batch, Real-Time, LLM systems; deployment API vs model signature | [ml-system-types.md](concepts/ml-system-types.md) |
| **MLOps Principles** | AI testing pyramid (offline+online), CI/CD, versioning, reproducibility | [mlops-principles.md](concepts/mlops-principles.md) |
| **Governance** | Lineage, schematized tags, versioning strategy, audit logs | [governance.md](concepts/governance.md) |

## Patterns

| Pattern | Use Case | File |
|---------|----------|------|
| **Feature Pipeline** | Data sources, CDC vs polling, orchestrators, WAP pattern | [feature-pipeline.md](patterns/feature-pipeline.md) |
| **Training Pipeline** | Feature selection, model architecture rules, hyperparameter tuning, model cards | [training-pipeline.md](patterns/training-pipeline.md) |
| **Inference Pipeline** | Batch/online/streaming inference, KServe, deployment API, ODT consistency | [inference-pipeline.md](patterns/inference-pipeline.md) |
| **Point-in-Time Joins** | ASOF LEFT JOIN, temporal join rules, training without data leakage | [point-in-time.md](patterns/point-in-time.md) |
| **Feature Monitoring** | Drift types, NannyML CBPE/DLE, agent traces, guardrails | [feature-monitoring.md](patterns/feature-monitoring.md) |

## Core Principle

```
Any AI system = Feature Pipeline + Training Pipeline + Inference Pipeline
                              ↕                  ↕
                         [Feature Store] ← shared data layer → [Model Registry]
```

## MVPS Development Process (from Ch. 2)

```
1. Define prediction problem + KPI
2. Identify data sources
3. Feature pipeline → Feature Store (MITs only)
4. Training pipeline → Model Registry (with performance gate)
5. Inference pipeline → Predictions
6. UI (Streamlit / Gradio)
7. Monitor and iterate
```

## Quick Decision Guide

| Need | Use |
|------|-----|
| Predictions on schedule | Batch ML System + Batch Inference Pipeline |
| Predictions on request (<100ms) | Real-Time ML System + Online Inference Pipeline |
| RAG / embeddings / agents | LLM ML System + Vector DB + Feature Store |
| Share features across models | Feature Store + Feature Groups |
| Consistent train/serve features | Feature Views + Point-in-Time Joins |
| Avoid training-serving skew | MITs in feature pipeline, MDTs in shared code |
| Model performance without labels | NannyML CBPE (classification) or DLE (regression) |
| Compliance / audit | Schematized tags + Lineage graph |
| Schema evolution | Version feature groups (bump integer version) |
