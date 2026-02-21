# SDD - Spec-Driven Development

> 5-phase development workflow: Brainstorm → Define → Design → Build → Ship

## Active Features

| Feature | Phase | Status | Document |
|---------|-------|--------|----------|
| FEATURE_STORE_MLOPS | Build | Complete | [BUILD_REPORT](reports/BUILD_REPORT_FEATURE_STORE_MLOPS.md) |

## Documents

| Document | Description |
|----------|-------------|
| [BRAINSTORM_FEATURE_STORE_MLOPS.md](features/BRAINSTORM_FEATURE_STORE_MLOPS.md) | Exploração inicial e decisões |
| [DEFINE_FEATURE_STORE_MLOPS.md](features/DEFINE_FEATURE_STORE_MLOPS.md) | Requisitos e acceptance criteria |
| [DESIGN_FEATURE_STORE_MLOPS.md](features/DESIGN_FEATURE_STORE_MLOPS.md) | Arquitetura técnica e code patterns |
| [BUILD_REPORT_FEATURE_STORE_MLOPS.md](reports/BUILD_REPORT_FEATURE_STORE_MLOPS.md) | Relatório de implementação |

## Commands

| Command | Phase | Purpose |
|---------|-------|---------|
| `/brainstorm` | 0 | Explore ideas through dialogue |
| `/define` | 1 | Capture and validate requirements |
| `/design` | 2 | Create architecture specification |
| `/build` | 3 | Execute implementation |
| `/ship` | 4 | Archive with lessons learned |

## Folder Structure

```
.claude/sdd/
├── _index.md           # This file
├── features/           # Active feature documents
├── reports/            # Build reports
├── archive/            # Shipped features
└── templates/          # Document templates
```

## Next Step

```bash
/ship .claude/sdd/features/DEFINE_FEATURE_STORE_MLOPS.md
```
