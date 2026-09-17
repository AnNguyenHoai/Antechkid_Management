# EP-ARCH-04.8 — Service Transaction Consistency

## Purpose
Normalize application-service transaction ownership after EP-ARCH-04.7 established that repositories receive and use application-owned sessions without owning lifecycle.

## Contract

1. Application services are the transaction boundary for mutations that use an application-owned session.
2. Repositories must never call `commit()` or `rollback()`.
3. A service method that owns a commit must also define an explicit exception rollback path in that same transaction scope.
4. Rollback must be executed before the exception escapes the service method.
5. Read-only service methods must not commit or rollback merely because they opened a session context.
6. Nested service calls must not create an undocumented transaction boundary that commits independently from the caller's logical mutation. Existing behavior that intentionally opens an independent session must remain explicit and is outside this gate.
7. The gate is source-driven and applies to every `*_service.py` module, not only a hand-maintained allowlist.

## Scope for this change

EP-ARCH-04.8 introduces the regression gate first and normalizes service transaction handling where the repository currently owns the transaction through a local session context. This task does not introduce a new unit-of-work abstraction or change repository APIs.

## Required validation

```powershell
pytest -q tests\test_ep_arch_04_8_service_transaction_consistency.py
pytest -q tests\test_ep_arch_04_7_dependency_direction_lifecycle.py
pytest -q tests\test_ep_arch_04_6_repository_api_contract.py
pytest -q
```
