# EP-ARCH-04.5 — Repository Consumer & API Contract Audit

## Baseline

`main_repos@03e52df00a2e6ecf48446c2f7389978ab918e7e2`

## Scope

This task audits the application-service consumers of the RepositoryProvider and the public API surface of concrete repositories after EP-ARCH-04.4 removed raw `BaseRepository.session` exposure.

The target dependency direction is:

```text
Application Service
        |
        v
RepositoryProvider
        |
        v
Concrete Repository
        |
        v
SQLAlchemy Session
```

## Findings

### Finding 1 — Provider consumer surface is dynamically enumerable

Application services consume repositories through `_repository_provider.<factory>(session)`. The provider protocol is the authoritative factory surface.

Status: **PASS / ENFORCED**

The EP-ARCH-04.5 regression gate dynamically discovers service consumers and rejects provider factory calls absent from `RepositoryProvider`.

### Finding 2 — Concrete repository construction remains forbidden in application services

The global service boundary must not drift back to `ConcreteRepository(...)` construction.

Status: **PASS / ENFORCED**

### Finding 3 — Raw repository Session access is forbidden

Consumers must not recover the SQLAlchemy `Session` from repository objects through `.session` or an equivalent public accessor.

Status: **PASS / ENFORCED**

### Finding 4 — Repository transaction/session escape hatches are forbidden

Concrete repository public APIs must not expose `session()`, `commit()`, or `rollback()` methods.

Status: **PASS / ENFORCED**

### Finding 5 — Repository directionality remains one-way

Repositories must not import application services.

Status: **PASS / ENFORCED**

## Regression Gate

`tests/test_ep_arch_04_5_repository_consumer_api_contract.py` dynamically discovers:

1. all application services;
2. all RepositoryProvider factory names;
3. all provider factories consumed by services;
4. all concrete repository modules;
5. all concrete repository public methods.

It then enforces the consumer/API contracts above.

## Non-goals

- No business behavior changes.
- No repository implementation rewrite.
- No transaction policy changes.
- No introduction of Unit of Work.
- No repository-to-repository dependency refactor.

## Validation

The baseline commit is exactly the commit specified for this task. The implementation is intentionally limited to a source-derived architecture regression gate and its documentation.

Run the dedicated EP-ARCH-04.5 tests and then the full CenterManager pytest suite before merge.
