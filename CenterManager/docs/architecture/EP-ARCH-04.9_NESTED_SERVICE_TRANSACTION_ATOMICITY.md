# EP-ARCH-04.9 — Nested Service Transaction & Atomicity Audit

## Baseline

`main_repos@320663d623d0b72e57ed9140b785f177e5daa066`

## Objective

Audit service composition and transaction ownership without introducing a Unit of Work or changing production behavior.

## Contract

```text
Application Service A
        |
        +---- RepositoryProvider ----> repositories
        |
        +---- Application Service B
                  |
                  X no hidden independent transaction
```

A logical mutation must not silently call another service that owns an independent commit boundary. Service composition itself is inventoried dynamically; only calls into methods proven by source analysis to contain `commit()` are considered transaction-owning nested calls.

## Baseline findings

### 1. The original 04.9 gate was too broad

The first implementation treated every service-looking call inside a committing method as a nested transaction violation. This incorrectly classified ordinary permission checks and best-effort audit calls as transaction-owning composition. It also required manual docstrings on dozens of existing methods even when the child service did not commit.

The corrected gate uses a conservative source-driven check:

- resolve service aliases created by assignments;
- identify service methods that actually contain `commit()`;
- flag only a caller that commits inside an application-owned session and invokes one of those transaction-owning child methods;
- exclude the existing `AuditService` best-effort independent boundary.

### 2. Best-effort audit remains an intentional independent boundary

`PermissionService._audit()` calls `AuditService.record(...)` through a separate session and intentionally swallows audit failures. This remains unchanged and is not treated as business-transaction nesting by the regression gate.

A future product-safe task may evaluate caller-transaction participation for audit logging.

### 3. Repository transaction primitives are explicitly guarded

Repositories must not call low-level transaction/connection primitives such as `begin()`, `begin_nested()`, `commit()`, `rollback()`, or `exec_driver_sql()` through their private session/connection objects.

## Enforced invariants

1. Service composition inventory is dynamically derived from every `*_service.py` file and deterministically ordered.
2. A committing service must not synchronously invoke a known transaction-owning child service through a hidden independent boundary.
3. `AuditService` remains an explicit best-effort independent operation until separately redesigned.
4. Repositories must not manipulate transaction state through low-level Session/Connection transaction primitives.
5. No production behavior or UnitOfWork abstraction is introduced by this task.

## Validation

Run from `CenterManager`:

```powershell
pytest -q tests\test_ep_arch_04_9_nested_service_transaction_atomicity.py
pytest -q tests\test_ep_arch_04_8_service_transaction_consistency.py
pytest -q tests\test_ep_arch_04_7_dependency_direction_lifecycle.py
pytest -q tests\test_ep_arch_04_6_repository_api_contract.py
pytest -q
```
