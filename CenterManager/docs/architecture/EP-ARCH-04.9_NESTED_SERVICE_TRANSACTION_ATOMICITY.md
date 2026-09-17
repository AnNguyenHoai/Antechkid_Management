# EP-ARCH-04.9 — Nested Service Transaction & Atomicity Audit

## Baseline

`main_repos@320663d623d0b72e57ed9140b785f177e5daa066`

## Objective

Audit the boundary between application-service composition and transaction ownership after EP-ARCH-04.8.

The goal is not to introduce a new Unit of Work abstraction. The goal is to make hidden transaction boundaries visible and prevent future service composition from accidentally splitting one logical mutation across independent transactions.

## Target architecture

```text
Application Service A
        |
        +---- RepositoryProvider ----> repositories
        |
        +---- Application Service B
                  |
                  X no hidden independent commit
```

A caller that owns a logical mutation must be able to reason about the complete mutation as one transaction unless an independent operation is intentionally documented and explicitly isolated.

## Findings at the requested baseline

### 1. Service composition is a missing global contract

EP-ARCH-04.8 validates commit/rollback behavior inside individual service methods, but it does not validate transaction boundaries across service-to-service composition.

The new EP-ARCH-04.9 source gate inventories service composition and checks committing methods that also compose another service.

### 2. Best-effort audit currently forms an intentional independent transaction

`PermissionService._audit()` constructs `AuditService` and calls `AuditService.record(...)` from a separate service/session boundary while swallowing audit failures. This is intentionally treated as an explicit exception in this audit contract because changing it would alter failure semantics for administration workflows.

This is a documented follow-up candidate, not a production behavior change in EP-ARCH-04.9.

### 3. Repository transaction primitives require stronger protection

EP-ARCH-04.7 prevents repositories from creating/owning Session and engine lifecycles, while EP-ARCH-04.8 prevents repository `commit()` / `rollback()` calls. That still leaves lower-level transaction primitives such as `begin()`, `begin_nested()`, and `exec_driver_sql()` capable of manipulating transaction state from inside repositories.

EP-ARCH-04.9 adds a regression gate for those primitives.

## Enforced contract

1. Service composition must be source-discoverable across the complete `*_service.py` tree.
2. A committing service method that also composes another service must have an explicit transaction-boundary explanation rather than silently creating a nested independent boundary.
3. Intentional independent service operations are narrowly allowlisted and documented.
4. Repositories must not manipulate transaction state through low-level session/connection transaction primitives.
5. This task does not change production behavior, repository APIs, or introduce UnitOfWork.

## Known follow-up

`PermissionService._audit()` should be reconsidered in a separate product-safe task. The current behavior intentionally treats audit storage as best-effort and independent from the caller mutation. Converting it to caller-transaction participation would require reviewing existing callers and failure expectations first.

## Validation

Run from `CenterManager`:

```powershell
pytest -q tests\test_ep_arch_04_9_nested_service_transaction_atomicity.py
pytest -q tests\test_ep_arch_04_8_service_transaction_consistency.py
pytest -q tests\test_ep_arch_04_7_dependency_direction_lifecycle.py
pytest -q tests\test_ep_arch_04_6_repository_api_contract.py
pytest -q
```
