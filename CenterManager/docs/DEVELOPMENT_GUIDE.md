# CenterManager — Development Guide

Status: **CURRENT DEVELOPER GUIDE**  
Updated: 2026-09-24

This guide describes how to work on the current CenterManager repository. Standing Codex/agent rules live in the repository-root `AGENTS.md`. Task-specific implementation requirements belong in GitHub Issues.

## 1. Supported development environment

CI is the reference environment:

- Windows (`windows-latest`)
- Python 3.10
- PySide6 desktop UI
- SQLite + SQLAlchemy 2.x
- Alembic
- pytest

Other Python versions may work locally, but new code must remain compatible with the CI baseline unless an explicit task changes it.

## 2. Setup

From `CenterManager/`:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS development environments:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## 3. Run the application

Use the repository's current launcher from `CenterManager/`:

```bash
python run.py
```

The application bootstrap is implemented in `src/centermanager/app.py`.

Important startup behavior:

- runtime/config/logging initialize first;
- the platform bootstrap initializes runtime context;
- configured Git synchronization occurs before the production DB is opened;
- true local/offline mode initializes the local runtime DB when no valid Git config exists;
- Alembic upgrades the runtime DB to head;
- login/permission context is established before workspace services become active.

Do not bypass this startup sequence in production code.

## 4. Tests

Run focused tests while developing:

```bash
python -m pytest tests/test_some_feature.py -q
```

Run the full suite before handoff when required by the Issue:

```bash
python -m pytest
```

GitHub Actions runs the full suite on Windows/Python 3.10 with JUnit reporting and timeout protection. Architecture gates are implemented as pytest tests and run in the same suite.

Do not hard-code expected global test counts in documentation; the suite changes continuously.

For Qt tests in headless environments, use the same environment assumptions as CI where applicable (`QT_QPA_PLATFORM=offscreen`).

## 5. Required development flow

Feature work follows the issue-driven flow documented in `AGENTS.md`:

```text
Product/Architecture
    ↓
GitHub Issue
    ↓
feature branch from specified base SHA
    ↓
implementation
    ↓
focused tests → fix until green
    ↓
full relevant/local tests
    ↓
architecture/lint gates
    ↓
git diff self-review
    ↓
commit + push
    ↓
Pull Request to main_repos
    ↓
GitHub Actions
    ↓
independent review
    ↓
human review/merge
```

Never implement feature work directly on `main_repos` unless the human explicitly requests a direct documentation/administrative update.

## 6. Source-of-truth hierarchy

For implementation work:

1. explicit human instruction;
2. approved domain/specification documents;
3. assigned GitHub Issue;
4. architecture/repository conventions;
5. existing implementation/tests.

Existing code is not automatically the target behavior when an approved specification intentionally changes it.

## 7. Current package structure

Key packages under `src/centermanager/`:

- `ui/` — PySide6 application shell, workspace UI and design system;
- `services/` — application/domain use cases and policies;
- `repositories/` — query/persistence layer and repository provider;
- `models/` — SQLAlchemy persisted models;
- `dto/` — read/projection contracts;
- `database/` — engine, migration/bootstrap helpers and seed behavior;
- `platform/` — runtime bootstrap, collaboration, synchronization and platform services;
- `core/` — paths, configuration, clock, current-user context and logging;
- `events/` — event bus and handlers;
- `export/` — export-oriented support.

`modules/` is not the current home of feature implementations. Do not create a new domain package there merely because older documentation suggested a future module layout.

## 8. Architecture rules

Normal dependency direction:

```text
UI → Service → Repository abstraction/provider → ORM → SQLite
```

Rules:

- no SQLAlchemy session/query logic in UI;
- no business validation duplicated in views;
- service authorization remains authoritative even when UI projects permissions;
- repositories own persistence/query mechanics;
- services should use repository-provider abstractions where established;
- do not introduce direct concrete repository imports when an architecture gate requires provider ownership;
- avoid direct service-level `session.add/flush/delete/query` when repository-owned persistence is the established contract;
- do not duplicate canonical domain resolvers/normalizers across layers.

See `docs/ARCHITECTURE.md` and architecture tests for enforceable boundaries.

## 9. Workspaces

The current UI is workspace-oriented (`student_workspace`, `class_workspace`, `finance_workspace`, `employee_workspace`, `admin_workspace`, etc.). Workspaces own presentation/workflow context, but application services/repositories remain shared packages today.

Do not perform broad package reorganization as part of an unrelated feature task.

## 10. Collaboration and synchronization

Git-backed synchronization/edit-session behavior is owned by `platform/`.

Business services must not:

- shell out to Git for domain workflows;
- implement their own synchronization;
- modify collaboration metadata directly;
- treat WRITE mode as a substitute for capability authorization.

When Git collaboration is configured, startup synchronization is authoritative; the application must not silently continue with a stale local DB after authoritative synchronization fails.

## 11. Database changes

Schema changes require Alembic migrations.

Before adding a migration:

- inspect the current migration head/chain;
- inspect affected models/repositories/services;
- preserve historical data;
- make backfill rules deterministic;
- do not guess ambiguous historical financial/domain values;
- add/update migration regression tests when the project has a chain contract.

Do not edit historical applied migrations solely to make a new feature easier.

## 12. Finance work

Finance Wallet V2 business rules are governed by:

```text
src: docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md
```

Progress/evidence is tracked in:

```text
docs/finance/FINANCE_WALLET_V2_IMPLEMENTATION_TRACKER.md
```

The Domain Spec wins over stale legacy behavior/tests when the spec explicitly changes the contract. Historical financial data must not be silently reclassified.

## 13. Paths and files

Use `centermanager.core.paths` rather than hard-coded absolute filesystem paths.

Use the owning service/platform API for attachments, exports, runtime metadata and synchronized assets. Do not assume an old Google Drive Desktop synchronization flow.

## 14. Configuration

Use the existing configuration APIs rather than reading arbitrary config files directly from business code.

Example:

```python
from centermanager.core.config import get_config

config = get_config()
```

## 15. Logging

Use module loggers:

```python
import logging
logger = logging.getLogger(__name__)
```

Preserve diagnostic context. Do not swallow exceptions with `except Exception: pass`.

## 16. Clock and deterministic tests

Where the application already exposes an application clock (`centermanager.core.clock`), use it for business-date semantics instead of `date.today()`/`datetime.now()` directly. This keeps tests deterministic and aligns domain behavior across services.

## 17. Coding conventions

Prefer:

- type hints on public/new interfaces;
- small cohesive functions;
- explicit domain concepts;
- existing DTOs/services/repository abstractions;
- comments explaining decisions rather than restating code;
- minimal, reviewable diffs.

Avoid:

- speculative abstractions;
- unrelated refactors/format churn;
- duplicated business logic;
- broad catch-all exception suppression;
- hard-coded row caps for financial totals;
- test-only production hacks.

## 18. Git hygiene

Before committing:

```bash
git status
git diff
git diff --stat
```

Verify:

- branch started from the Issue-specified base;
- no generated/debug files are included;
- no secrets are included;
- no unrelated formatting churn exists;
- migrations/docs/tests match the implementation;
- PR targets `main_repos` unless the Issue says otherwise.

## 19. CI failures

When GitHub Actions fails, inspect the exact failing test/log. Classify the failure before changing code:

- implementation defect;
- integration regression;
- stale compatibility expectation;
- legitimate architecture violation;
- false-positive test.

Fix the underlying contract, not merely the symptom.

## 20. Documentation

Documentation has distinct roles:

- `ARCHITECTURE.md` — current implementation architecture;
- `Bussiness/ARCHITECTURE_V2.md` — product/workspace architecture and mapping;
- `Deployment_Docs/` — platform direction/principles/protocols;
- domain specs — authoritative business/domain contracts;
- GitHub Issues — task implementation contracts;
- root `AGENTS.md` — standing coding-agent rules.

When a feature materially changes one of these contracts, update the owning document rather than adding another competing architecture description.