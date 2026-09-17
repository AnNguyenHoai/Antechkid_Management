# EP-ARCH-04.6 — Repository API & Lifecycle Contract Audit

## Baseline

`main_repos@b6a0f0651c9b81cc5a72e6d346a8c2dc723526c6`

## Scope

EP-ARCH-04.6 closes the remaining repository-contract gap after EP-ARCH-04.2, EP-ARCH-04.3, EP-ARCH-04.4, and EP-ARCH-04.5.

The target architecture remains:

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
Private SQLAlchemy Session
```

This slice establishes a source-driven contract for repository API and lifecycle shape without changing production behavior.

## Findings

### Finding 1 — BaseRepository must expose explicit persistence/query operations

The shared repository foundation must provide the explicit operations already used by application services and concrete repositories:

- `add`
- `delete`
- `get_by_id`
- `list_all`
- `count`
- `flush`
- `refresh`

Status: **PASS / ENFORCED**

### Finding 2 — Raw Session and transaction control remain non-public

`BaseRepository` and concrete repositories must not expose public `session()`, `commit()`, or `rollback()` APIs. The raw SQLAlchemy session remains private as `_session`.

Status: **PASS / ENFORCED**

EP-ARCH-04.3 remains authoritative for transaction ownership; EP-ARCH-04.4/04.5 remain authoritative for session encapsulation and consumer boundaries.

### Finding 3 — Concrete repository module/class shape must stay deterministic

Each concrete `*_repository.py` must define exactly one concrete `*Repository` class. This prevents silent provider ambiguity when a repository module evolves.

Status: **PASS / ENFORCED**

### Finding 4 — Repository ORM access must remain behind private session storage

Repositories must not use a public `self.session` path for ORM/query/persistence operations.

Status: **PASS / ENFORCED**

### Finding 5 — Repository construction receives an explicit Session dependency

Concrete repositories must accept `session` explicitly in their constructor. Construction remains owned by `RepositoryProvider`; the repository does not create or replace the application-owned session lifecycle.

Status: **PASS / ENFORCED**

## Regression Gate

`tests/test_ep_arch_04_6_repository_api_contract.py` dynamically discovers the repository tree and verifies:

1. the required explicit `BaseRepository` operations exist;
2. public session/transaction escape hatches do not exist;
3. each concrete repository module has one concrete repository class;
4. repositories do not invoke forbidden operations through `self.session`;
5. application services do not recover raw repository session/transaction APIs;
6. concrete repository constructors receive `session` explicitly.

## Relationship to previous architecture gates

- **EP-ARCH-04.1** — global service boundary.
- **EP-ARCH-04.2** — RepositoryProvider completeness.
- **EP-ARCH-04.3** — service-owned transaction boundary.
- **EP-ARCH-04.4** — repository session encapsulation.
- **EP-ARCH-04.5** — repository consumer/provider API contract.
- **EP-ARCH-04.6** — repository API and lifecycle shape.

These gates are complementary and intentionally do not replace one another.

## Non-goals

- No business behavior changes.
- No repository query rewrite.
- No transaction-policy change.
- No Unit of Work introduction.
- No repository-to-repository dependency refactor.
- No change to the existing provider implementation contract.

## Validation

Run the dedicated EP-ARCH-04.6 tests and then the full CenterManager pytest suite before merge.
