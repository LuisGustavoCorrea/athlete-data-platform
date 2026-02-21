# BRAINSTORM: MLOps Corrections + Monitoring Layer

> Sessão de exploração para identificar gaps críticos no pipeline ML existente e definir a camada de MLOps completa

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | MLOPS_CORRECTIONS |
| **Date** | 2026-02-21 |
| **Author** | brainstorm-agent + feature-store-architect (Jim Dowling O'Reilly book) |
| **Status** | Ready for Define |
| **Relates To** | [DESIGN_FEATURE_STORE_MLOPS.md](./DESIGN_FEATURE_STORE_MLOPS.md) (ciclo anterior — implementado) |

---

## Initial Idea

**Raw Input:**
> "Monte um brainstorm para aplicar o end to end até a entrega de valor com o ML, esteira completa"

**Context Gathered:**
- Ciclo SDD anterior (2026-02-18) implementou: Feature Store, Feature Engineering, Time Estimator, Batch Inference, DABs jobs
- Código implementado: `src/feature_engineering/`, `src/ml/time_estimator/`, `src/notebooks/`, `resources/*.yml`
- Revisão completa do código revelou gaps críticos de correção e ausência total de camada de MLOps
- Referência: livro "Building ML Systems with a Feature Store" (Jim Dowling, O'Reilly)

---

## Riscos Críticos Identificados (P0)

| # | Risco | Arquivo | Impacto |
|---|-------|---------|---------|
| R1 | **Data Leakage** — join manual por data exata em vez de ASOF JOIN com `timestamp_lookup_key` | `src/ml/time_estimator/train.py:L64` | MAE inflado, modelo não confiável |
| R2 | **Invalid evaluation** — `train_test_split` aleatório em série temporal CTL/ATL | `src/ml/time_estimator/train.py:L141` | Métricas otimistas, MAE subestimado |
| R3 | **Sem performance gate** — modelo ruim pode ir para produção sem controle | `src/ml/time_estimator/train.py` | Qualidade de modelo não garantida |
| R4 | **Inference bypassa Feature Store** — lineage quebrado no Unity Catalog | `src/ml/time_estimator/inference.py` | Governança nula, schema drift silencioso |
| R5 | **Gold table overwrite** — histórico de predições perdido diariamente | `src/ml/time_estimator/inference.py:L156` | Monitoring de prediction drift impossível |

---

## Discovery Questions & Answers

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Qual o foco principal da correção? | Corrigir P0s + adicionar monitoring + CI/CD | Esteira completa end-to-end |
| 2 | Monitoring com ou sem ground truth? | Sem ground truth inicialmente (atleta precisa reportar provas) | NannyML DLE para label-free estimation |
| 3 | Retraining: scheduled ou event-driven? | Mensal (scheduled) + trigger por performance | Trigger duplo |
| 4 | Dashboard para atleta: quando? | Após pipeline estável — Databricks SQL Dashboard | Fase 2 de valor |
| 5 | Champion/challenger: necessário agora? | Sim, parte do MLOps baseline | Aliases @champion/@challenger |
| 6 | CI/CD: GitHub Actions? | Sim, DABs deploy automatizado | tests + bundle validate + deploy |
| 7 | Overtraining alert: como entregar? | Email via job notification | Simples, já tem infra |

---

## Architecture Overview

```
══════════════════════════════════════════════════════════════════════
  ATHLETE DATA PLATFORM — COMPLETE TARGET ARCHITECTURE (2026-02-21)
══════════════════════════════════════════════════════════════════════

SOURCE                  INGESTION                    STORAGE
──────                  ─────────                    ───────
Strava API ──[OAuth]──► Auto Loader ──────────────► RAW (ADLS Gen2)
                        (scheduled 05:00 BRT)            │
                        [CORRIGIR: add schedule]          ▼
                                                    BRONZE (Delta)
                                                         │
                                               [dedup + data quality]
                                                         │
                                                    SILVER (Delta)

══════════════ FEATURE PIPELINE (daily 06:00 BRT) ══════════════════

Silver ──► [Feature_Activity.py] ──► activity_features (MIT: TSS, HR zones)
       ──► [Feature_Rolling.py]  ──► rolling_features  (MIT: CTL/ATL/TSB/ACWR)
       ──► [Feature_AthleteProfile.py] ──► athlete_profile (SCD Type 0) [NOVO]
       ──► [Feature_RaceResults.py]    ──► race_results (labels) [NOVO]

[ADD: WAP pattern + row count assertion]
[ADD: freshness check]

══════════════ TRAINING PIPELINE (monthly + performance trigger) ══

[Train_Time_Estimator.py]
- FeatureLookup(timestamp_lookup_key="race_date") [CORRIGIR]
- TimeSeriesSplit(gap=43)                          [CORRIGIR]
- Performance gate: MAE < 180s (3 min)             [ADICIONAR]
- NannyML DLE fit on test set + save artifact      [ADICIONAR]
- SHAP feature importance                          [ADICIONAR]

MODEL REGISTRY (Unity Catalog)
  @champion ← produção
  @challenger ← candidato novo [ADICIONAR]

══════════════ INFERENCE PIPELINE (daily 06:30 BRT) ══════════════

[Batch_Inference.py]
- fe.score_batch(@champion) [CORRIGIR: usar Feature Engineering API]
- Gold table: append + prediction_date [CORRIGIR: era overwrite]
- inference_log table: features + predictions [ADICIONAR]
- NannyML DLE apply: estimated MAE sem labels [ADICIONAR]

══════════════ MONITORING (daily, after inference) ═══════════════

[Setup_Monitoring.py] — one-time setup [NOVO]
- Databricks Lakehouse Monitoring em rolling_features
- Databricks Lakehouse Monitoring em inference_log
- KS tests em CTL, ACWR, pace_trend

[Monitor_Feature_Drift.py] — daily check [NOVO]
- NannyML DLE apply
- Freshness check
- Alert threshold

══════════════ VALUE DELIVERY ════════════════════════════════════

Gold Table ──► Databricks SQL Dashboard [NOVO]
           ──► Email alert (overtraining risk) [NOVO]
           ──► [Futuro] REST API / Streamlit

══════════════ CI/CD (GitHub Actions) ═══════════════════════════

.github/workflows/ci.yml     [NOVO] pytest + bundle validate
.github/workflows/deploy.yml [NOVO] bundle deploy --target prod
```

---

## Selected Approach

| Attribute | Value |
|-----------|-------|
| **Chosen** | Correções P0 + MLOps Baseline (Champion/Challenger + NannyML DLE + Lakehouse Monitoring + CI/CD) |
| **Reasoning** | Sem as correções P0, as predições são não-confiáveis. MLOps baseline fecha o loop de observabilidade. |
| **Out of Scope** | Online serving, Streamlit app, multi-user, hyperparameter tuning (Optuna) |

---

## Features Removed (YAGNI)

| Feature Sugerida | Razão Removida | Pode Adicionar Depois? |
|-----------------|----------------|------------------------|
| Databricks Model Serving (online) | Batch suficiente agora | Yes |
| Streamlit app | Databricks SQL Dashboard suficiente para MVP | Yes |
| Multi-user OAuth | Single athlete ainda | Yes |
| Hyperparameter tuning (Optuna) | GBM defaults razoáveis para dataset pequeno | Yes |
| CBPE (Confidence-Based Performance Estimation) | DLE suficiente, CBPE para regressão é DLE | N/A |
| Race results webhook | Strava já tem race activities no silver | Yes (automático) |
| Overtraining ML model | Regras ACWR/TSB suficientes para MVP | Yes |

---

## Deliverables do Ciclo

| # | Entregável | Tipo | Impacto |
|---|-----------|------|---------|
| 1 | Fix `train.py`: FeatureLookup + TimeSeriesSplit | Correção P0 | Elimina data leakage |
| 2 | Fix `train.py`: performance gate | Correção P0 | Garante qualidade de modelo |
| 3 | Fix `train.py`: NannyML DLE fit | Novo | Habilita monitoring sem labels |
| 4 | Fix `inference.py`: fe.score_batch + append mode | Correção P0 | Restaura lineage + histórico |
| 5 | New `inference.py`: inference_log table | Novo | Habilita drift monitoring |
| 6 | Fix `strava-pipeline.yml`: add schedule | Correção P0 | Garante freshness de dados |
| 7 | New `Feature_RaceResults.py` + notebook | Novo | Labels como feature group |
| 8 | New `Setup_Monitoring.py` | Novo | Lakehouse Monitoring setup |
| 9 | New `Monitor_Feature_Drift.py` | Novo | NannyML DLE apply diário |
| 10 | New `.github/workflows/ci.yml` | Novo | Automated testing |
| 11 | New `.github/workflows/deploy.yml` | Novo | Automated deployment |
| 12 | Databricks SQL Dashboard (YAML config) | Novo | Valor ao atleta |
| 13 | Champion/challenger alias workflow | Novo | MLOps governance |

---

## Incremental Validations

| Section | Presented | Feedback |
|---------|-----------|----------|
| Riscos P0 identificados | ✅ | Confirmado — implementar |
| Approach NannyML DLE (label-free) | ✅ | Confirmado |
| Novo ciclo SDD separado | ✅ | Confirmado — novo ciclo |
| Retraining mensal + trigger | ✅ | Confirmado |
| YAGNI (online serving fora) | ✅ | Confirmado |

---

## Session Summary

| Metric | Value |
|--------|-------|
| Riscos Críticos Identificados | 5 (P0) |
| Gaps de MLOps | 8 |
| Features Removidas (YAGNI) | 7 |
| Duração | ~60 min |

---

## Next Step

**Ready for:** `/define .claude/sdd/features/BRAINSTORM_MLOPS_CORRECTIONS.md`
