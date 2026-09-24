# CenterManager — Current Implementation Architecture

Status: **CURRENT IMPLEMENTATION REFERENCE**  
Updated: 2026-09-24

This document describes the architecture that exists in the repository today. Conceptual product/workspace direction is documented separately in `docs/Bussiness/ARCHITECTURE_V2.md`. Long-term platform principles live under `docs/Deployment_Docs/`.

## 1. Runtime shape

CenterManager is a PySide6 desktop application with a local SQLite runtime database, SQLAlchemy 2.x ORM, Alembic migrations, application services, repository abstractions, a workspace-oriented UI, and an optional Git-backed collaboration/synchronization platform.

```text
PySide6 UI / Workspaces
        ↓
Application Services / Policies / Read Models
        ↓
Repository Provider + Repositories
        ↓
SQLAlchemy ORM / Alembic
        ↓
SQLite runtime database

Cross-cutting platform:
Bootstrap · Authentication/Authorization · Events · Collaboration
Synchronization · Runtime Context · Notifications · Logging · Paths
```

The application entry point is `src/centermanager/app.py`.

## 2. Layer responsibilities

| Layer | Current responsibility |
|---|---|
| UI (`ui/`) | Render workspaces, collect input, project capability/domain state, call services. UI must not own persistence or canonical business rules. |
| Services (`services/`) | Application use cases, business/domain validation, authorization orchestration, transaction boundaries, read-model composition. |
| Repositories (`repositories/`) | SQLAlchemy queries and persistence mechanics. Services use repository abstractions/provider rather than concrete ORM access where that boundary exists. |
| Models (`models/`) | Persisted SQLAlchemy domain state. |
| DTOs (`dto/`) | Read/projection contracts crossing service/UI boundaries. |
| Platform (`platform/`) | Bootstrap, runtime context, collaboration/edit-session protocol, synchronization providers, workspace registry, notifications and version/runtime infrastructure. |
| Core (`core/`) | Paths, config, clock, current user, logging and other low-level application facilities. |
| Events (`events/`) | In-process domain/application events and handlers for cross-feature refresh/projection. |

Architecture tests in `tests/` enforce important dependency boundaries. They are part of the architecture contract, not optional style checks.

## 3. UI and workspace architecture

The current UI is implemented under `src/centermanager/ui/` and already contains workspace packages such as:

- `student_workspace/`
- `class_workspace/`
- `finance_workspace/`
- `employee_workspace/`
- `admin_workspace/`
- `home/`
- shared `design_system/`

The application shell and `MainWindow` coordinate navigation. Workspaces are product/business boundaries, but the Python implementation is intentionally transitional: services and repositories are currently mostly flat packages rather than nested per-workspace packages.

Do not move files merely to match a conceptual diagram. Structural refactors require an explicit task because import stability and architecture tests matter.

## 4. Service and repository boundaries

The normal dependency direction is:

```text
UI → Service → Repository abstraction/provider → SQLAlchemy → SQLite
```

Rules:

- UI must not issue ORM queries or manipulate sessions directly.
- UI authorization is projection only; service/domain authorization remains authoritative.
- Services must not duplicate repository query mechanics.
- Repositories must not contain UI behavior.
- Canonical domain resolvers/normalizers should have one owner and be reused, not copied across layers.
- Persistence side effects should be explicit. Avoid ORM mapper-event side effects for application workflows unless a documented infrastructure concern requires them.

## 5. Database lifecycle

The production runtime uses SQLite with SQLAlchemy and Alembic.

Startup order in `app.py` is significant:

1. initialize paths/config/logging;
2. bootstrap platform/runtime context;
3. resolve optional Git configuration;
4. when Git synchronization is configured, synchronize the authoritative repository state before opening the production database;
5. materialize/initialize the runtime database for true local/offline mode when needed;
6. create SQLAlchemy engine/session factory;
7. upgrade schema to current Alembic head;
8. authenticate user and initialize application/platform services;
9. start collaboration/synchronization behavior and UI.

Never open a stale local database as an automatic fallback after a configured authoritative Git synchronization fails.

## 6. Local mode and Git-backed collaboration

CenterManager supports two runtime situations:

### Local/offline mode

When no valid Git collaboration configuration is present, the application can run against its local runtime database.

### Configured Git collaboration mode

When configured, Git synchronization is part of the authoritative runtime-data lifecycle. The platform owns synchronization/edit-session behavior; business services must not call Git directly.

This replaces the old documentation that described Google Drive Desktop as the application synchronization architecture. Google Drive links may still appear as business data/URLs, but Google Drive Desktop is not the core database synchronization mechanism.

## 7. Collaboration and write safety

Collaboration is a platform concern. Business/UI modules consume collaboration state rather than implementing synchronization themselves.

Important concepts include:

- runtime context/lifecycle;
- collaboration WRITE/read state;
- edit-session/write transaction coordination;
- synchronization manager/provider;
- data-consistency barriers before writer ownership;
- permission/capability checks at service boundaries.

WRITE mode alone is not authorization. A mutation can additionally require a fine-grained capability and domain-state preconditions.

## 8. Authorization

Authentication occurs during application startup. Current-user context is established after login.

Authorization rules are service/application concerns. UI controls may be hidden/disabled for usability, but a visible/enabled control must never be the sole enforcement mechanism.

Use the existing permission registry/services; do not invent duplicate permission identifiers in UI code.

## 9. Events

`events/` provides in-process event publication/handlers for decoupled projections and cross-page refresh behavior.

Events are not a substitute for an atomic database transaction. Financial or other critical persistence must commit correctly before best-effort post-commit projection/event work can be treated as successful UI refresh behavior.

## 10. Finance architecture

Finance Wallet V2 has a dedicated approved domain contract:

`docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md`

That file is authoritative for FinancePeriod, Wallet, realized Income/Expense, Outstanding, Settlement and Finance capability projection. The implementation tracker records progress/evidence only.

Finance business rules must not be recreated in UI code.

## 11. Filesystem/runtime data

Path resolution belongs to `core.paths` and platform/runtime infrastructure. Do not hard-code absolute paths.

Runtime artifacts can include:

- SQLite database/runtime repository data;
- logs;
- exports;
- attachments/documents;
- collaboration/synchronization metadata.

Structured business state belongs in the database unless a specific domain contract states otherwise. Files are referenced/persisted according to their owning service and path abstractions.

## 12. Packaging and deployment

The repository uses a `src/` package layout and includes Windows packaging/release support. Development starts through the project launcher/runtime entry points; packaged deployments must continue to resolve writable runtime paths separately from bundled application code.

Deployment details belong in `docs/DEPLOYMENT.md` and `docs/Deployment_Docs/` rather than being duplicated here.

## 13. Testing and architecture gates

The canonical CI workflow is `.github/workflows/pytest-suite.yml`:

- Windows runner;
- Python 3.10;
- runtime + development requirements installed;
- full `python -m pytest` suite;
- architecture tests run as part of pytest;
- JUnit and visual-regression evidence uploaded when available.

Local focused tests are expected during development; the full GitHub Actions suite remains an independent integration gate.

## 14. Documentation hierarchy

When documentation differs, use this interpretation:

1. approved domain-specific specs govern their domain;
2. this file describes current implementation architecture;
3. `Bussiness/ARCHITECTURE_V2.md` describes product/workspace architecture and current mapping;
4. `Deployment_Docs/` describes long-term platform principles/protocols;
5. task-specific GitHub Issues define implementation scope without overriding approved domain contracts.

`AGENTS.md` at repository root defines standing engineering rules for Codex/automation.