# BRAINSTORM: Feature Store + MLOps para Athlete Platform

> Exploratory session to clarify intent and approach before requirements capture

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | FEATURE_STORE_MLOPS |
| **Date** | 2026-02-18 |
| **Author** | brainstorm-agent + medallion-architect + running-performance-specialist |
| **Status** | Ready for Define |

---

## Initial Idea

**Raw Input:**
> "Quero uma Feature Store completa com MLOps no Databricks para criar relatórios e diagnósticos de atividades de atletas, com métricas importantes e previsões usando ML. Cada atleta terá sua visão individual, e depois expandir para coaches/nutricionistas."

**Context Gathered:**
- Projeto já possui arquitetura Medallion (Bronze → Silver) funcionando
- Pipeline Strava via ADF + Databricks com AutoLoader
- Unity Catalog configurado (`uc_athlete_data`)
- DABs em implementação para IaC
- Dados disponíveis: activities, athlete, sub_activity (com HR)
- Gold layer não implementado
- Nenhum modelo ML em produção

**Technical Context Observed (for Define):**

| Aspect | Observation | Implication |
|--------|-------------|-------------|
| Likely Location | `src/notebooks/` + novo módulo `src/feature_engineering/` | Modularização do código de features |
| Relevant KB Domains | databricks, delta-lake, mlflow, feature-store | Criar KBs específicos |
| IaC Patterns | DABs (databricks.yml, resources/) | Usar DABs para jobs de feature engineering |
| Data Sources | Bronze tables via streaming | Features podem ser streaming ou batch |

---

## Discovery Questions & Answers

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Qual a prioridade do MVP? (Métricas básicas / Previsões / Diagnóstico / Multi-atleta) | **Todas** - escopo completo | Arquitetura robusta desde início |
| 2 | Qual abordagem para Feature Store? (Nativo Databricks / Delta manual / FS + Unity Catalog) | **Databricks Feature Store nativo com Unity Catalog** | APIs nativas, governance, versionamento automático |
| 3 | Qual granularidade das features? (Por atividade / Semanal / Rolling / Todas) | **Todas as granularidades** | Múltiplas tabelas de features |
| 4 | Sub_activity tem Heart Rate? | **Sim** | Podemos implementar Tier 3 (métricas avançadas de HR) |
| 5 | Stack MLOps? (Databricks nativo / Híbrido / Custom) | **100% Databricks** | MLflow + Model Registry + Serving nativos |
| 6 | Estrutura do catálogo FS? | Schema `feature_store` dentro de `uc_athlete_data` | Governança centralizada |
| 7 | Ordem dos modelos ML? | C → A → B → D → E (valor rápido primeiro) | Estimador de tempo primeiro |
| 8 | Multi-atleta quando? | MVP 1 single-tenant, design multi-tenant | `athlete_id` como partition key |
| 9 | Análise de performance do pipeline atual? | Não (otimizar durante implementação) | Foco em design novo |

---

## Sample Data Inventory

| Type | Location | Count | Notes |
|------|----------|-------|-------|
| Bronze activities | `uc_athlete_data.bronze.strava_activities` | ~1000+ | JSON estruturado, timestamps |
| Bronze sub_activity | `uc_athlete_data.bronze.strava_sub_activity` | ~5000+ | Splits/laps com HR |
| Silver activities | `uc_athlete_data.silver.strava_activities` | ~1000+ | 9+ métricas derivadas |
| Transformation code | `src/notebooks/Silver_activities.py` | 1 | Padrões de transformação |
| Quality rules | `notebooks/dataquality_rules_strava.py` | 1 | Regras de validação |

**How samples will be used:**
- Silver activities como base para feature engineering
- Sub_activity para métricas de HR zones
- Padrões de transformação existentes como referência
- Dados reais para validação de features

---

## Approaches Explored

### Approach A: 100% Databricks Native Stack ⭐ Recommended

**Description:** Usar Feature Store nativo do Databricks integrado com Unity Catalog, MLflow para experiment tracking, Model Registry no UC, e Databricks Model Serving.

**Pros:**
- Integração nativa entre todos os componentes
- Governance centralizada no Unity Catalog
- Versionamento automático de features
- Point-in-time correctness para training
- Online serving com baixa latência
- Lineage completo (data → features → models → predictions)
- Aprendizado do ecossistema Databricks completo

**Cons:**
- Vendor lock-in (Databricks)
- Custo de compute para serving
- Curva de aprendizado das APIs

**Why Recommended:** Você já tem UC configurado, DABs em implementação, e quer aprender o ecossistema. Stack unificado reduz complexidade operacional.

---

### Approach B: Híbrido (Databricks + Azure ML)

**Description:** Feature Store no Databricks, mas Model Serving no Azure ML.

**Pros:**
- Mais opções de serving (containers, endpoints)
- Integração com outros serviços Azure

**Cons:**
- Complexidade operacional dobrada
- Duas plataformas para gerenciar
- Perda de lineage integrado

---

### Approach C: Delta Tables Manuais

**Description:** Criar tabelas Delta organizadas manualmente sem usar APIs de Feature Store.

**Pros:**
- Mais simples inicialmente
- Sem dependência de APIs específicas

**Cons:**
- Sem versionamento automático
- Sem point-in-time lookup
- Sem online serving nativo
- JOINs manuais no training

---

## Selected Approach

| Attribute | Value |
|-----------|-------|
| **Chosen** | Approach A (100% Databricks Native Stack) |
| **User Confirmation** | 2026-02-18 |
| **Reasoning** | Aprendizado completo do ecossistema + governance unificada + menor complexidade operacional |

---

## Key Decisions Made

| # | Decision | Rationale | Alternative Rejected |
|---|----------|-----------|----------------------|
| 1 | Usar Feature Store APIs (não Delta manual) | Versionamento, lineage, point-in-time | Tabelas Delta normais |
| 2 | Schema `feature_store` no catálogo existente | Governance centralizada | Catálogo separado |
| 3 | 3 tiers de métricas (Básico + Training Load + HR) | Cobertura completa, dados disponíveis | Apenas métricas básicas |
| 4 | MVP single-tenant com design multi-tenant | Rápido para valor, fácil escalar | Multi-tenant desde início |
| 5 | Modelos na ordem C → A → B → D → E | Valor rápido primeiro | Começar pelo mais complexo |
| 6 | 4 tabelas de features por granularidade | Flexibilidade para diferentes use cases | Tabela única |

---

## Features Removed (YAGNI)

| Feature Suggested | Reason Removed | Can Add Later? |
|-------------------|----------------|----------------|
| Real-time streaming features | Batch suficiente para MVP | Yes |
| Feature Store online serving | Não precisa inferência <100ms agora | Yes |
| Integração com wearables além Strava | Foco no Strava primeiro | Yes |
| Dashboard interativo | Foco em dados/ML primeiro | Yes |
| Notificações push | Não é core do MVP | Yes |

---

## Incremental Validations

| Section | Presented | User Feedback | Adjusted? |
|---------|-----------|---------------|-----------|
| Arquitetura Medallion + FS | ✅ | Confirmado | No |
| Estrutura do catálogo UC | ✅ | Confirmado schema feature_store | No |
| Métricas de corrida (3 tiers) | ✅ | Todas, incluindo HR | No |
| Stack MLOps | ✅ | 100% Databricks para aprender | No |
| Ordem dos modelos | ✅ | C → A → B → D → E | No |
| Multi-tenant design | ✅ | MVP1 single, design multi | No |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ATHLETE DATA PLATFORM - TARGET ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STRAVA API                                                                 │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────────┐             │
│  │  RAW    │───▶│ BRONZE  │───▶│ SILVER  │───▶│ FEATURE      │             │
│  │  (ADLS) │    │         │    │         │    │ STORE        │             │
│  └─────────┘    └─────────┘    └─────────┘    └──────────────┘             │
│                                                       │                     │
│                                                       ▼                     │
│                                              ┌──────────────┐               │
│                                              │   MLFLOW     │               │
│                                              │  Experiments │               │
│                                              └──────────────┘               │
│                                                       │                     │
│                                                       ▼                     │
│                                              ┌──────────────┐               │
│                                              │   MODEL      │               │
│                                              │  REGISTRY    │               │
│                                              │   (UC)       │               │
│                                              └──────────────┘               │
│                                                       │                     │
│                                                       ▼                     │
│  ┌─────────┐                                ┌──────────────┐               │
│  │  GOLD   │◀───────────────────────────────│   MODEL      │               │
│  │ (Final) │    predictions written back    │  INFERENCE   │               │
│  └─────────┘                                └──────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

UNITY CATALOG STRUCTURE:
========================
uc_athlete_data
├── bronze
│   ├── strava_activities
│   ├── strava_athlete
│   └── strava_sub_activity
├── silver
│   ├── strava_activities (9+ métricas)
│   └── strava_sub_activity
├── feature_store (NEW)
│   ├── activity_features         # Por atividade
│   ├── athlete_daily_features    # Agregado diário
│   ├── athlete_weekly_features   # Agregado semanal
│   └── athlete_rolling_features  # Janelas móveis (7d, 30d, 90d)
├── gold (NEW)
│   ├── athlete_predictions       # Saídas dos modelos
│   ├── athlete_metrics_summary   # KPIs agregados
│   └── training_recommendations  # Recomendações
└── models (UC Model Registry)
    ├── time_estimator            # Modelo C
    ├── pace_predictor            # Modelo A
    ├── overtraining_detector     # Modelo B
    ├── athlete_clustering        # Modelo D
    └── training_recommender      # Modelo E
```

---

## Feature Tables Design

### 1. activity_features (Primary Keys: athlete_id, activity_id)

| Feature | Type | Description | Source |
|---------|------|-------------|--------|
| `athlete_id` | STRING | PK | silver.activities |
| `activity_id` | LONG | PK | silver.activities |
| `event_timestamp` | TIMESTAMP | Point-in-time key | silver.activities |
| `distance_km` | DOUBLE | Distância em km | silver.activities |
| `pace_min_km` | DOUBLE | Pace em min/km | silver.activities |
| `elevation_gain_m` | DOUBLE | Ganho de elevação | silver.activities |
| `elevation_per_km` | DOUBLE | Elevação por km | calculated |
| `moving_time_min` | DOUBLE | Tempo em movimento | silver.activities |
| `avg_hr` | DOUBLE | HR médio | silver.sub_activity |
| `max_hr` | DOUBLE | HR máximo | silver.sub_activity |
| `hr_zone_1_pct` | DOUBLE | % tempo zona 1 | calculated |
| `hr_zone_2_pct` | DOUBLE | % tempo zona 2 | calculated |
| `hr_zone_3_pct` | DOUBLE | % tempo zona 3 | calculated |
| `hr_zone_4_pct` | DOUBLE | % tempo zona 4 | calculated |
| `hr_zone_5_pct` | DOUBLE | % tempo zona 5 | calculated |
| `estimated_tss` | DOUBLE | Training Stress Score | calculated |
| `intensity_factor` | DOUBLE | IF (pace/threshold) | calculated |
| `efficiency_index` | DOUBLE | Pace / HR | calculated |

### 2. athlete_weekly_features (Primary Keys: athlete_id, week_start)

| Feature | Type | Description |
|---------|------|-------------|
| `athlete_id` | STRING | PK |
| `week_start` | DATE | PK (Monday) |
| `weekly_distance_km` | DOUBLE | Total km na semana |
| `weekly_activities` | INT | Número de atividades |
| `weekly_tss` | DOUBLE | TSS total |
| `weekly_elevation_m` | DOUBLE | Elevação total |
| `avg_pace_week` | DOUBLE | Pace médio |
| `training_monotony` | DOUBLE | Monotonia (risco overtraining) |
| `training_strain` | DOUBLE | Strain (TSS × Monotonia) |

### 3. athlete_rolling_features (Primary Keys: athlete_id, as_of_date)

| Feature | Type | Description |
|---------|------|-------------|
| `athlete_id` | STRING | PK |
| `as_of_date` | DATE | PK |
| `ctl_42d` | DOUBLE | Chronic Training Load (fitness) |
| `atl_7d` | DOUBLE | Acute Training Load (fatigue) |
| `tsb` | DOUBLE | Training Stress Balance (form) |
| `acwr` | DOUBLE | Acute:Chronic Workload Ratio |
| `pace_trend_30d` | DOUBLE | Tendência de pace |
| `distance_trend_30d` | DOUBLE | Tendência de volume |
| `consistency_score` | DOUBLE | Regularidade de treino |

---

## ML Models Specification

### Model C: Time Estimator (First Priority)

| Attribute | Value |
|-----------|-------|
| **Objetivo** | Estimar tempo para completar 5K, 10K, 21K, 42K |
| **Tipo** | Regression |
| **Features** | CTL, pace_trend, recent_distances, elevation_factor |
| **Target** | predicted_time_seconds |
| **Algoritmo** | Gradient Boosting (XGBoost/LightGBM) |
| **Métricas** | MAE, RMSE, MAPE |

### Model A: Pace Predictor

| Attribute | Value |
|-----------|-------|
| **Objetivo** | Prever pace para próxima atividade |
| **Tipo** | Regression |
| **Features** | rolling_features, weather (futuro), elevation_planned |
| **Target** | predicted_pace_min_km |

### Model B: Overtraining Detector

| Attribute | Value |
|-----------|-------|
| **Objetivo** | Detectar risco de overtraining |
| **Tipo** | Binary Classification |
| **Features** | monotony, strain, ACWR, TSB, rest_days |
| **Target** | is_overtraining_risk (0/1) |

### Model D: Athlete Clustering

| Attribute | Value |
|-----------|-------|
| **Objetivo** | Agrupar atletas por perfil |
| **Tipo** | Unsupervised (Clustering) |
| **Features** | volume, intensity_distribution, consistency |
| **Output** | cluster_id, cluster_name |

### Model E: Training Recommender

| Attribute | Value |
|-----------|-------|
| **Objetivo** | Recomendar próximo treino |
| **Tipo** | Recommendation |
| **Features** | current_form, goals, history |
| **Output** | recommended_workout_type, intensity, duration |

---

## Suggested Requirements for /define

### Problem Statement (Draft)
Atletas precisam de métricas avançadas de performance, previsões de tempo para provas, e alertas de overtraining, atualmente indisponíveis na plataforma.

### Target Users (Draft)

| User | Pain Point |
|------|------------|
| Atleta Individual | Não sabe se está melhorando ou em risco de lesão |
| Atleta Competitivo | Não consegue estimar tempo para próxima prova |
| Coach (Futuro) | Não tem visão consolidada dos atletas |

### Success Criteria (Draft)
- [ ] Feature Store com 4 tabelas populadas e versionadas
- [ ] Modelo de estimativa de tempo com MAE < 3 minutos para 10K
- [ ] Pipeline de feature engineering automatizado (DABs)
- [ ] Lineage completo no Unity Catalog
- [ ] MLflow experiments com pelo menos 10 runs registrados
- [ ] Modelo registrado no UC Model Registry

### Constraints Identified
- Dados limitados a um atleta no MVP (single-tenant)
- Sem dados de clima/condições externas
- Heart Rate depende do dispositivo do atleta
- Compute budget do Databricks

### Out of Scope (Confirmed)
- Real-time streaming features
- Online serving (<100ms latency)
- Integração com outros wearables
- Dashboard interativo
- Notificações push
- Multi-tenant authentication

---

## Session Summary

| Metric | Value |
|--------|-------|
| Questions Asked | 9 |
| Approaches Explored | 3 |
| Features Removed (YAGNI) | 5 |
| Validations Completed | 6 |
| Duration | ~30 min |

---

## Next Step

**Ready for:** `/define .claude/sdd/features/BRAINSTORM_FEATURE_STORE_MLOPS.md`

---

## References

- [Predictive athlete performance modeling with ML](https://www.nature.com/articles/s41598-025-01438-9)
- [ML-based personalized training models for marathon](https://www.nature.com/articles/s41598-025-25369-7)
- [Running Smart with ML and Strava](https://medium.com/data-science/running-smart-with-machine-learning-and-strava-9ba186decde0)
- [Understanding Training Metrics CTL/ATL/TSS](https://www.evoq.bike/blog/2019/1/25/1-massive-reason-why-obsessing-over-your-ctl-can-ruin-your-race-season)
