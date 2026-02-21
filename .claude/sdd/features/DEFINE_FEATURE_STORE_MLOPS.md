# DEFINE: Feature Store + MLOps para Athlete Platform

> Plataforma completa de Feature Store e MLOps no Databricks para métricas de performance, previsões e diagnósticos de atletas usando dados do Strava.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | FEATURE_STORE_MLOPS |
| **Date** | 2026-02-18 |
| **Author** | define-agent |
| **Status** | Ready for Design |
| **Clarity Score** | 14/15 |
| **Brainstorm** | [BRAINSTORM_FEATURE_STORE_MLOPS.md](BRAINSTORM_FEATURE_STORE_MLOPS.md) |

---

## Problem Statement

Atletas que usam Strava não têm acesso a métricas avançadas de training load (CTL/ATL/TSB), previsões de tempo para provas, ou alertas de overtraining. Atualmente, esses insights requerem plataformas pagas como TrainingPeaks ou análise manual, resultando em treinos subótimos e risco aumentado de lesões.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| **Atleta Recreativo** | Corre 2-4x/semana | Não sabe se está melhorando ou treinando demais |
| **Atleta Competitivo** | Prepara para provas | Não consegue estimar tempo realista para próxima prova |
| **Coach** (Futuro) | Treina múltiplos atletas | Não tem visão consolidada de carga e risco de cada atleta |
| **Nutricionista** (Futuro) | Acompanha atletas | Não tem dados de volume/intensidade para ajustar dieta |

---

## Goals

| Priority | Goal |
|----------|------|
| **MUST** | Criar Feature Store com 4 tabelas de features (activity, daily, weekly, rolling) |
| **MUST** | Implementar cálculo de training load (TSS, CTL, ATL, TSB, ACWR) |
| **MUST** | Treinar e registrar modelo de estimativa de tempo (5K/10K/21K/42K) |
| **MUST** | Pipeline automatizado de feature engineering via DABs |
| **SHOULD** | Implementar detector de risco de overtraining |
| **SHOULD** | Criar tabela Gold com previsões e métricas agregadas |
| **COULD** | Implementar clustering de perfil de atleta |
| **COULD** | Criar recomendador de próximo treino |

---

## Success Criteria

Measurable outcomes:

- [ ] **FS-001**: 4 Feature Tables criadas no Unity Catalog com schema `feature_store`
- [ ] **FS-002**: Features versionadas via Databricks Feature Store APIs
- [ ] **FS-003**: Lineage completo visível no Unity Catalog (source → features → models)
- [ ] **ML-001**: Modelo de estimativa de tempo com MAE < 3 minutos para 10K
- [ ] **ML-002**: Modelo registrado no UC Model Registry com pelo menos 3 versões
- [ ] **ML-003**: MLflow experiments com mínimo 10 runs documentados
- [ ] **PIPE-001**: Job DABs executando feature engineering diariamente
- [ ] **PIPE-002**: Tempo de execução do pipeline < 10 minutos
- [ ] **DATA-001**: Features de training load calculadas para 100% das atividades
- [ ] **DATA-002**: HR zones calculadas para atividades com heart rate

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | Feature creation | Nova atividade no Silver | Job de feature engineering executa | Features inseridas em `activity_features` com todas as colunas |
| AT-002 | Training load calculation | Atleta com 30+ dias de histórico | Rolling features calculadas | CTL, ATL, TSB, ACWR com valores válidos (não null) |
| AT-003 | Time estimation | Atleta com 10+ corridas | Solicita previsão para 10K | Modelo retorna tempo estimado com intervalo de confiança |
| AT-004 | Point-in-time correctness | Training set criado para modelo | Features são lookupadas | Features correspondem ao estado no momento do evento, não atual |
| AT-005 | HR zones calculation | Atividade com heart rate | Features calculadas | 5 zonas de HR com percentuais somando 100% |
| AT-006 | Overtraining detection | Atleta com ACWR > 1.5 | Modelo de detecção executa | Flag `is_overtraining_risk = true` |
| AT-007 | Feature versioning | Feature table atualizada | Nova versão de feature adicionada | Versão anterior preservada, nova versão ativa |
| AT-008 | Pipeline idempotency | Job executa 2x no mesmo dia | Segunda execução | Sem duplicatas, mesmo resultado |
| AT-009 | Missing HR handling | Atividade sem heart rate | Features calculadas | HR features = null, outras features calculadas normalmente |
| AT-010 | Multi-athlete isolation | 2 atletas no sistema | Features calculadas | Cada atleta vê apenas suas próprias features |

---

## Out of Scope

Explicitly NOT included in this feature:

- **Real-time streaming features** - Batch processing suficiente para MVP
- **Online serving** (<100ms latency) - Não precisa inferência real-time agora
- **Integração com wearables** além Strava (Garmin, Polar, etc.)
- **Dashboard interativo** - Foco em dados/ML, visualização depois
- **Notificações push** - Não é core do MVP
- **Multi-tenant authentication** - MVP single-user, design multi-tenant
- **Weather/conditions data** - Não disponível via Strava API
- **Social features** - Comparação entre atletas
- **Mobile app** - Apenas backend/data

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| **Data** | Dados limitados a 1 atleta no MVP | Modelos treinados com dataset pequeno, pode precisar transfer learning |
| **Data** | Heart Rate depende do dispositivo | Algumas atividades não terão HR features |
| **Compute** | Budget de compute Databricks | Cluster Standard_DS3_v2 (1 worker), jobs devem ser eficientes |
| **Technical** | Unity Catalog já configurado | Usar catálogo `uc_athlete_data` existente |
| **Technical** | DABs em implementação | Jobs devem ser compatíveis com DABs (não notebooks legados) |
| **Timeline** | Projeto de aprendizado | Priorizar entendimento sobre velocidade |

---

## Technical Context

| Aspect | Value | Notes |
|--------|-------|-------|
| **Deployment Location** | `src/feature_engineering/` + `src/ml/` | Novos módulos Python |
| **Notebooks Location** | `src/notebooks/` | Jobs de feature engineering e training |
| **KB Domains** | databricks, delta-lake, mlflow, feature-store, spark | Criar KBs se necessário |
| **IaC Impact** | Modificar `resources/strava-pipeline.yml` | Adicionar jobs de feature engineering e ML |
| **Unity Catalog** | `uc_athlete_data.feature_store.*` | Novo schema |

**Deployment Structure:**

```
src/
├── notebooks/                    # Existente
│   ├── 01_bronze_load.py
│   ├── Silver_activities.py
│   └── Silver_SubActivity.py
├── feature_engineering/          # NOVO
│   ├── __init__.py
│   ├── activity_features.py      # Feature engineering por atividade
│   ├── rolling_features.py       # CTL, ATL, TSB, ACWR
│   ├── weekly_features.py        # Agregações semanais
│   └── feature_store_utils.py    # Helpers para FS API
└── ml/                           # NOVO
    ├── __init__.py
    ├── time_estimator/           # Modelo C
    │   ├── train.py
    │   ├── inference.py
    │   └── config.py
    └── overtraining_detector/    # Modelo B
        ├── train.py
        └── inference.py
```

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | Databricks Feature Store API disponível no workspace | Precisaria usar Delta tables manuais | [ ] Validar |
| A-002 | Unity Catalog suporta Model Registry | Precisaria usar MLflow Registry standalone | [ ] Validar |
| A-003 | Histórico de 30+ atividades suficiente para treinar modelo | Precisaria synthetic data ou transfer learning | [x] Sim |
| A-004 | Dados de sub_activity contêm HR para maioria das corridas | HR features teriam baixa cobertura | [ ] Validar % |
| A-005 | Cluster Standard_DS3_v2 suficiente para feature engineering | Precisaria upgrade de cluster | [ ] Validar |
| A-006 | DABs suporta jobs Python além de notebooks | Precisaria usar notebooks | [x] Sim |

---

## Data Requirements

### Input Data (Silver Layer)

| Table | Key Columns | Usage |
|-------|-------------|-------|
| `silver.strava_activities` | athlete_id, id, start_date, distance_km, pace_min_km, elapsed_time, moving_time, elevation | Base para activity_features |
| `silver.strava_sub_activity` | athlete_id, activity_id, split_id, average_heartrate, max_heartrate | HR zones calculation |

### Output Data (Feature Store)

| Table | Primary Keys | Timestamp Key | Features Count |
|-------|--------------|---------------|----------------|
| `feature_store.activity_features` | athlete_id, activity_id | event_timestamp | ~18 |
| `feature_store.athlete_daily_features` | athlete_id, activity_date | activity_date | ~10 |
| `feature_store.athlete_weekly_features` | athlete_id, week_start | week_start | ~12 |
| `feature_store.athlete_rolling_features` | athlete_id, as_of_date | as_of_date | ~15 |

---

## Feature Specifications

### Tier 1: Basic Metrics (From Silver)

| Feature | Formula | Source |
|---------|---------|--------|
| `distance_km` | Direct | silver.activities |
| `pace_min_km` | Direct | silver.activities |
| `elevation_gain_m` | Direct | silver.activities |
| `moving_time_min` | `moving_time / 60` | silver.activities |
| `elapsed_time_min` | `elapsed_time / 60` | silver.activities |
| `elevation_per_km` | `elevation_gain / distance_km` | Calculated |

### Tier 2: Training Load Metrics

| Feature | Formula | Description |
|---------|---------|-------------|
| `estimated_tss` | `(duration_min × IF²) / 60 × 100` | Training Stress Score |
| `intensity_factor` | `pace / threshold_pace` | Fator de intensidade |
| `ctl_42d` | `EMA(tss, 42 days)` | Chronic Training Load (Fitness) |
| `atl_7d` | `EMA(tss, 7 days)` | Acute Training Load (Fatigue) |
| `tsb` | `CTL - ATL` | Training Stress Balance (Form) |
| `acwr` | `ATL / CTL` | Acute:Chronic Workload Ratio |
| `training_monotony` | `avg(tss_7d) / stddev(tss_7d)` | Monotonia (risco overtraining) |
| `training_strain` | `sum(tss_7d) × monotony` | Strain total |

### Tier 3: Heart Rate Metrics

| Feature | Formula | Description |
|---------|---------|-------------|
| `avg_hr` | `avg(heartrate)` | HR médio da atividade |
| `max_hr` | `max(heartrate)` | HR máximo |
| `hr_zone_1_pct` | `time_in_zone_1 / total_time` | % tempo em zona 1 (recovery) |
| `hr_zone_2_pct` | `time_in_zone_2 / total_time` | % tempo em zona 2 (aerobic) |
| `hr_zone_3_pct` | `time_in_zone_3 / total_time` | % tempo em zona 3 (tempo) |
| `hr_zone_4_pct` | `time_in_zone_4 / total_time` | % tempo em zona 4 (threshold) |
| `hr_zone_5_pct` | `time_in_zone_5 / total_time` | % tempo em zona 5 (VO2max) |
| `efficiency_index` | `pace / avg_hr` | Eficiência cardíaca |

---

## Model Specifications

### Model C: Time Estimator (Priority 1)

| Attribute | Value |
|-----------|-------|
| **Objective** | Estimar tempo para completar distâncias padrão |
| **Type** | Multi-output Regression |
| **Targets** | `predicted_5k_sec`, `predicted_10k_sec`, `predicted_21k_sec`, `predicted_42k_sec` |
| **Features** | `ctl_42d`, `pace_trend_30d`, `best_pace_30d`, `avg_distance_30d`, `consistency_score` |
| **Algorithm** | XGBoost / LightGBM |
| **Metrics** | MAE, RMSE, MAPE |
| **Success** | MAE < 180 seconds (3 min) para 10K |

### Model B: Overtraining Detector (Priority 2)

| Attribute | Value |
|-----------|-------|
| **Objective** | Detectar risco de overtraining |
| **Type** | Binary Classification |
| **Target** | `is_overtraining_risk` (0/1) |
| **Features** | `acwr`, `tsb`, `training_monotony`, `training_strain`, `rest_days_7d` |
| **Algorithm** | Random Forest / XGBoost |
| **Metrics** | Precision, Recall, F1, AUC-ROC |
| **Success** | Recall > 0.8 (não perder casos de risco) |

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | 3 | Claro: atletas não têm métricas avançadas |
| Users | 3 | 4 tipos de usuários identificados |
| Goals | 3 | MUST/SHOULD/COULD bem definidos |
| Success | 3 | 10 critérios mensuráveis |
| Scope | 2 | Out of scope definido, mas algumas áreas cinzas em modelos D e E |
| **Total** | **14/15** | |

---

## Open Questions

1. **HR Zones Thresholds**: Usar zonas fixas (% do max HR) ou calcular baseado em dados do atleta?
   - **Recommendation**: Começar com zonas fixas (50-60%, 60-70%, 70-80%, 80-90%, 90-100% do max HR)

2. **Threshold Pace**: Como determinar o threshold pace para cálculo do IF?
   - **Recommendation**: Usar o pace médio dos últimos 30 dias como proxy inicial

3. **Cold Start**: Como lidar com atletas novos sem histórico?
   - **Recommendation**: Mínimo de 10 atividades para calcular features rolling, usar defaults antes

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-18 | define-agent | Initial version from BRAINSTORM |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_FEATURE_STORE_MLOPS.md`
