# CenterManager — Collaborative Architecture

Version: 1.1  
Status: **CURRENT PLATFORM ARCHITECTURE / DIRECTION**  
Updated: 2026-09-24

Depends on:

- `000_PLATFORM_VISION.md`
- `100_ARCHITECTURE_PRINCIPLES.md`

This document describes the collaboration/platform architecture at the level that should remain stable across implementation changes. Exact class/module names are defined by the current code and `docs/ARCHITECTURE.md`.

## 1. Purpose

CenterManager needs controlled multi-user operation without forcing the business domains to implement synchronization/deployment behavior themselves.

The collaboration platform owns runtime coordination around:

- startup/bootstrap;
- authoritative synchronization when configured;
- edit/write ownership;
- runtime context/state;
- synchronization/publishing;
- version metadata;
- notifications;
- consistency barriers/recovery behavior.

## 2. Current high-level shape

```text
Workspace UI
    ↓
Application / Domain Services
    ↓
Repositories / SQLite

        ↕ platform state/events

Platform
├── Bootstrap / Runtime Context
├── Collaboration Manager / Poller
├── Synchronization Manager
├── Runtime Sync Service
├── Git Synchronization Provider (configured mode)
├── Version / Metadata
└── Notifications
```

The Platform is a cross-cutting peer capability, not a database layer that every repository call must mechanically pass through.

## 3. Responsibilities

### Bootstrap/runtime context

Owns platform initialization, lifecycle/runtime state and workspace/platform registration required before business UI becomes active.

### Collaboration

Owns controlled write/edit ownership and collaboration state. Business/UI modules observe/use this state; they do not create their own lock/sync protocol.

### Synchronization

Owns pull/publish/update behavior and configured synchronization provider interactions.

### Git provider

Git is the currently implemented collaboration backend for configured deployments. It is infrastructure, not business language.

### Version/metadata

Owns collaboration/runtime version metadata needed to detect/publish/refresh state.

### Notifications/events

Expose platform changes/errors to the application without embedding business rules in synchronization infrastructure.

## 4. Runtime modes

### Local/offline mode

When no valid Git collaboration configuration exists, CenterManager can operate with a local runtime database.

### Configured collaborative mode

When Git collaboration is configured:

1. platform/bootstrap resolves configuration/provider;
2. startup synchronization runs before opening the production runtime DB;
3. synchronized repository data is authoritative for runtime DB materialization;
4. failure of authoritative startup sync prevents startup rather than silently using stale local data;
5. background/runtime synchronization and collaboration coordination continue after login/startup.

## 5. Write ownership

CenterManager favors deterministic controlled writing rather than real-time multi-writer merge semantics.

Conceptually:

```text
READ / no writer
    ↓ request write
write ownership/edit session granted
    ↓
application transaction(s)
    ↓
publish/synchronize according to platform protocol
    ↓
release/transition ownership
```

Exact protocol/state names are governed by the current collaboration implementation and protocol documents, not by old conceptual state diagrams.

WRITE ownership is necessary for applicable mutations but does not grant permission. Service authorization and domain-state guards remain authoritative.

## 6. Synchronization boundaries

Business domains must not:

- execute Git commands for normal domain workflows;
- know repository URL/token details;
- publish versions directly;
- implement their own polling/heartbeat protocol;
- decide stale-vs-authoritative runtime DB fallback independently.

Platform code must not:

- calculate tuition/accounting rules;
- own Student/Class business validation;
- replace service authorization;
- create business mutations merely to make synchronization easier.

## 7. Persistence and synchronization

Database transactions and synchronization are different correctness boundaries.

A business transaction should remain atomic at the database/service boundary. Synchronization/publish behavior is coordinated by the platform/write transaction protocol around those transactions.

Do not hide core business persistence inside synchronization callbacks or Git operations.

## 8. Events and refresh

Platform/application events can trigger workspace refresh and projection updates.

Events reduce UI coupling, but they do not replace authoritative service reads or atomic database transactions.

Workspaces should react to platform/data changes through established shell/event/refresh mechanisms rather than each workspace continuously polling Git/storage.

## 9. Deployment backend evolution

Current implementation has a Git-backed synchronization provider. Future server/hybrid providers are possible, but they are not current production facts.

New backends should reuse stable platform contracts where practical. Do not build speculative adapters until a concrete deployment requirement exists.

## 10. Authorization and collaboration

Three independent questions must remain distinguishable:

1. Does the user currently have collaboration WRITE ownership/mode?
2. Does the user have the required capability/permission?
3. Does the domain state allow the operation (for example an open FinancePeriod ledger)?

An operation may require all three.

## 11. Workspace relationship

Workspaces participate in collaboration through application/platform context. They do not own synchronization infrastructure.

A workspace may:

- reflect read/write state;
- request/participate in established edit-session behavior;
- refresh when version/data events indicate change;
- disable mutation controls when state/capability/domain rules require it.

A workspace may not become a second CollaborationManager.

## 12. Recovery and failure

Correct failure behavior is explicit:

- configured authoritative startup synchronization failure blocks stale startup;
- sync/publish failures surface diagnostics/state to platform/UI;
- database transaction failures roll back according to service/repository boundaries;
- already committed domain transactions must not be reported as failed solely because best-effort post-commit projection failed.

## 13. Architectural invariants

- Collaboration/synchronization remains a Platform concern.
- Business/domain rules remain outside platform infrastructure.
- Git is an implementation/provider detail, not business terminology.
- Controlled write ownership is not authorization.
- Local mode and configured collaborative mode are both explicit runtime states.
- No workspace implements independent synchronization logic.
- Current code is authoritative for exact component names; this document describes responsibilities/boundaries.

## 14. Relationship to implementation

Important current implementation areas include:

- `src/centermanager/platform/`
- `src/centermanager/platform/collaboration/`
- `src/centermanager/platform/synchronization/`
- `src/centermanager/core/git_locator.py`
- `src/centermanager/services/git_config_service.py`
- `src/centermanager/services/write_transaction.py`
- application bootstrap in `src/centermanager/app.py`

When implementation intentionally changes these responsibilities, update this document as part of the architecture change rather than preserving a stale diagram.