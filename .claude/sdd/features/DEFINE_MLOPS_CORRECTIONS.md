# DEFINE: MLOps Corrections + Monitoring Layer

> Correção de gaps críticos de data leakage e avaliação inválida no pipeline ML, adição de camada de monitoring (Lakehouse Monitoring + NannyML DLE) e CI/CD automatizado via GitHub Actions + DABs.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | MLOPS_CORRECTIONS |
| **Date** | 2026-02-21 |
| **Author** | define-agent |
| **Status** | Ready for Design |
| **Clarity Score** | 14/15 |
| **Brainstorm** | [BRAINSTORM_MLOPS_CORRECTIONS.md](BRAINSTORM_MLOPS_CORRECTIONS.md) |
| **Relates To** | [DESIGN_FEATURE_STORE_MLOPS.md](./DESIGN_FEATURE_STORE_MLOPS.md) |

---

## Problem Statement

O pipeline ML do Athlete Data Platform possui 5 riscos críticos ativos: (1) data leakage no training set por uso de join manual em vez de ASOF JOIN com `timestamp_lookup_key`; (2) avaliação inválida com `train_test_split` aleatório em série temporal; (3) ausência de performance gate antes do registro de modelos; (4) inference que bypassa o Feature Engineering API quebrando o lineage no Unity Catalog; (5) gold table em modo `overwrite` destruindo o histórico de predições diariamente. Adicionalmente, não existe nenhuma camada de monitoring, CI/CD, ou entrega de valor ao atleta.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| **Atleta Individual** | Consome predições de tempo de prova | Predições podem ser não-confiáveis por data leakage |
| **Desenvolvedor** | Mantém o pipeline | Sem CI/CD, deploys manuais, sem feedback de qualidade |
| **Pipeline (sistema)** | Executa feature engineering + inference | Sem monitoring, falhas silenciosas não detectadas |

---

## Goals

| Priority | Goal |
|----------|------|
| **MUST** | Eliminar data leakage: substituir join manual por `FeatureLookup(timestamp_lookup_key)` |
| **MUST** | Corrigir avaliação de modelo: `TimeSeriesSplit(gap=43)` em vez de `train_test_split` aleatório |
| **MUST** | Adicionar performance gate: só registrar modelo se `MAE < 180s (3 min)` |
| **MUST** | Corrigir inference: usar `fe.score_batch()` e mudar gold table para `append` mode |
| **MUST** | Criar inference log table com features + predictions (input para monitoring) |
| **MUST** | Adicionar `schedule:` no `strava-pipeline.yml` (05:00 BRT) |
| **SHOULD** | Fit NannyML DLE no test set durante training e salvar como artefato MLflow |
| **SHOULD** | Setup Databricks Lakehouse Monitoring em `rolling_features` e `inference_log` |
| **SHOULD** | Criar Feature_RaceResults.py: labels como feature group com `timestamp_keys` |
| **SHOULD** | GitHub Actions CI: `pytest + bundle validate` em Pull Requests |
| **SHOULD** | GitHub Actions Deploy: `bundle deploy --target prod` em merge para `main` |
| **COULD** | Champion/challenger alias workflow (@champion, @challenger) |
| **COULD** | Freshness check no topo de Feature_Rolling.py |
| **COULD** | Monitor_Feature_Drift.py com NannyML DLE apply diário |
| **COULD** | Databricks SQL Dashboard para visualização do atleta |

---

## Success Criteria

Measurable outcomes:

- [ ] **P0-001**: `train.py` usa `FeatureLookup(timestamp_lookup_key="race_date")` — sem join manual por data exata
- [ ] **P0-002**: `train.py` usa `TimeSeriesSplit` com `gap >= 43` dias — sem `train_test_split` aleatório
- [ ] **P0-003**: `train.py` tem gate que falha se `MAE > 180s` e não registra o modelo
- [ ] **P0-004**: `inference.py` usa `fe.score_batch(model_uri=".../@champion")` em vez de Pandas UDF manual
- [ ] **P0-005**: Gold table escrita em modo `append` com coluna `prediction_date`
- [ ] **P0-006**: `strava-pipeline.yml` tem `schedule: quartz_cron_expression: "0 0 5 * * ?"` com `pause_status` parametrizado
- [ ] **MON-001**: `uc_athlete_data.monitoring.inference_log` tabela criada e populada após cada inference run
- [ ] **MON-002**: Lakehouse Monitor configurado em `athlete_rolling_features` com granularidade diária e semanal
- [ ] **MON-003**: NannyML DLE estimator salvo como artefato MLflow no run de training
- [ ] **CI-001**: `pytest tests/` passa em PR antes do merge
- [ ] **CI-002**: `databricks bundle validate` passa em PR antes do merge
- [ ] **CI-003**: `databricks bundle deploy --target prod` executa automaticamente em merge para `main`

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | Sem data leakage | Training set criado para atleta com 20 corridas | `prepare_training_data()` executa | Features são do estado em `race_date` (não futuro) |
| AT-002 | Split temporal correto | 20 corridas em 6 meses | `train_time_estimator()` divide os dados | Test set é posterior ao train set com gap de 43+ dias |
| AT-003 | Performance gate ativo | Modelo treina com MAE = 400s (6.7 min) | `train_time_estimator()` finaliza | Modelo NÃO registrado no UC; MLflow run status = FAILED |
| AT-004 | Performance gate passa | Modelo treina com MAE = 120s (2 min) | `train_time_estimator()` finaliza | Modelo registrado com alias @challenger |
| AT-005 | Inference via Feature Store API | Spine de athlete_ids enviada | `batch_inference()` executa | `fe.score_batch()` chamado; lineage visível no UC |
| AT-006 | Gold table append mode | Inference executada dia 1 e dia 2 | Dia 2 inference executa | Gold table tem linhas dos 2 dias, não apenas dia 2 |
| AT-007 | Inference log criado | Inference executa hoje | Job completa | `monitoring.inference_log` tem 1 linha por atleta com features + predictions + `prediction_date` |
| AT-008 | Strava schedule ativo | `strava-pipeline.yml` deployado | 05:00 BRT todo dia | Job executa automaticamente (não manual) |
| AT-009 | CI bloqueia PR com testes falhando | PR com bug em `calculate_tss()` | GitHub Actions executa | PR bloqueado, `pytest` falha visível |
| AT-010 | DLE artifact salvo | Training run completa com MAE < 180s | Artefato MLflow inspecionado | `monitoring/dle_estimator.pkl` presente no run |

---

## Out of Scope

Explicitly NOT included in this feature:

- **Databricks Model Serving** (online serving, <100ms latency) — batch suficiente
- **Streamlit / Mobile App** — Databricks SQL Dashboard é o MVP de UI
- **Multi-user OAuth** — single athlete ainda
- **Hyperparameter tuning (Optuna)** — GBM defaults são razoáveis para dataset pequeno
- **NannyML CBPE** — DLE cobre o caso de regressão de forma equivalente
- **Overtraining ML model** (Modelo B) — regras ACWR/TSB/monotony suficientes para detecção
- **Athlete Clustering** (Modelo D) — fora do escopo deste ciclo
- **Training Recommender** (Modelo E) — fora do escopo deste ciclo
- **A/B testing framework** — champion/challenger por alias é suficiente
- **New Azure resources** — sem novos recursos (só código + DABs YAML)

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| **Data** | Dataset pequeno (~30 corridas por atleta) — `TimeSeriesSplit` com gap=43d pode deixar poucos pontos no test set | Aceito: qualidade > quantidade de amostras |
| **Infra** | NannyML DLE requer chunk mínimo de dados para estimar performance | Chunk size = atividade semanal; alertar se dados insuficientes |
| **Infra** | Lakehouse Monitoring cria tabelas adicionais em `uc_athlete_data.monitoring` | Schema `monitoring` precisa existir |
| **CI/CD** | GitHub Actions precisa de `DATABRICKS_HOST` e `DATABRICKS_TOKEN` como secrets | Configurar secrets no repo antes do deploy |
| **Compat** | `fe.score_batch()` requer que o modelo foi logado via `fe.log_model()` | Modelos legados precisam ser re-treinados |

---

## Technical Context

| Aspect | Value | Notes |
|--------|-------|-------|
| **Deployment Location** | Modificar `src/ml/`, `resources/`. Criar `src/notebooks/`, `.github/workflows/` | In-place corrections + new files |
| **KB Domains** | Databricks Feature Engineering API, Databricks Lakehouse Monitoring, GitHub Actions + DABs CI/CD | Conforme selecionado |
| **IaC Impact** | Modificar `resources/strava-pipeline.yml` e `resources/ml-pipeline.yml`. Criar `.github/workflows/*.yml` | Sem novos recursos Azure |
| **Unity Catalog** | Novo schema `uc_athlete_data.monitoring` para inference_log e drift_metrics | Criado via notebook ou DABs |

**File Manifest (Changes):**

```
MODIFY:
  src/ml/time_estimator/train.py         ← P0-001, P0-002, P0-003, MON-003
  src/ml/time_estimator/inference.py     ← P0-004, P0-005, MON-001
  resources/strava-pipeline.yml          ← P0-006
  resources/ml-pipeline.yml             ← add inference_log task

CREATE:
  src/notebooks/Feature_RaceResults.py   ← race_results feature group (labels)
  src/notebooks/Setup_Monitoring.py      ← Lakehouse Monitoring one-time setup
  src/notebooks/Monitor_Feature_Drift.py ← NannyML DLE apply daily (COULD)
  .github/workflows/ci.yml              ← CI-001, CI-002
  .github/workflows/deploy.yml          ← CI-003
```

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | `fe.score_batch()` funciona com modelos treinados via `fe.log_model()` | Inference precisa de abordagem alternativa | [ ] Validar no Databricks |
| A-002 | NannyML instalável no cluster Databricks (pypi) | Precisaria de custom wheel | [ ] Verificar `pyproject.toml` |
| A-003 | Lakehouse Monitoring disponível no tier do workspace | Precisaria de Delta Live Tables ou manual | [ ] Verificar workspace tier |
| A-004 | GitHub Secrets configuráveis no repositório (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`) | CI/CD não funciona | [ ] Configurar secrets |
| A-005 | Dataset de race activities é suficiente para `TimeSeriesSplit(gap=43)` | Modelo falha por falta de dados de test | [ ] Aceito como risco |
| A-006 | `race_activities` podem ser identificadas no Silver pelo tipo de atividade e distância | Feature_RaceResults.py funciona | [x] Sim, filtro por `distance_bucket` existe |

---

## Data Requirements

### Inputs

| Source | Usage |
|--------|-------|
| `src/ml/time_estimator/train.py` | Corrigir join + split |
| `src/ml/time_estimator/inference.py` | Corrigir modo write + usar FS API |
| `uc_athlete_data.feature_store.athlete_rolling_features` | Input para training set via FeatureLookup |
| `uc_athlete_data.silver.strava_activities` | Fonte das race labels |

### Outputs

| Table | Mode | Notes |
|-------|------|-------|
| `uc_athlete_data.gold.athlete_predictions` | append | Histórico preservado por `prediction_date` |
| `uc_athlete_data.monitoring.inference_log` | append | Features + predictions por dia |
| MLflow artifact: `monitoring/dle_estimator.pkl` | write once | Salvo no training run |

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | 3 | 5 riscos concretos com arquivo e linha identificados |
| Users | 2 | Atleta + Dev + Pipeline identificados; Coach é futuro |
| Goals | 3 | MUST/SHOULD/COULD com itens acionáveis |
| Success | 3 | 12 critérios mensuráveis e testáveis |
| Scope | 3 | Out of scope explícito com 9 itens |
| **Total** | **14/15** | ✅ Acima do mínimo 12/15 |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-21 | define-agent | Initial version from BRAINSTORM_MLOPS_CORRECTIONS |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_MLOPS_CORRECTIONS.md`
