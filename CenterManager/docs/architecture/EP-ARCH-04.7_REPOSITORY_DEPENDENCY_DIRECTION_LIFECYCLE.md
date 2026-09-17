# EP-ARCH-04.7 — Repository Dependency Direction & Session Lifecycle

## Baseline

`main_repos@b10bf068d49d52eb5bb8dcff2a3ee4eaac501b9f`

## Objective

Lock the repository layer's dependency direction and session lifecycle ownership after EP-ARCH-04.1 through EP-ARCH-04.6.

## Architecture contract

Application services own application orchestration and transaction completion. `RepositoryProvider` supplies concrete repositories. Concrete repositories receive an already-created SQLAlchemy `Session` and keep that dependency private.

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
SQLAlchemy ORM
```

The repository layer must not depend upward into application services or presentation layers, and repositories must not create or own the Session/engine lifecycle.

## Enforced invariants

1. Repository modules must not import `centermanager.services` or presentation/application-layer modules such as controllers, UI, views, or application orchestration packages.
2. Repository modules must not import SQLAlchemy engine/session factory APIs such as `create_engine`, `sessionmaker`, `async_sessionmaker`, or scoped-session factories.
3. Concrete repositories must not instantiate `Session`, `AsyncSession`, engines, session factories, or transaction contexts.
4. Concrete repository constructors must accept the application-owned `session` explicitly and store it as private `self._session`.
5. Repository classes must not expose public `session`, `commit`, `rollback`, or `begin` lifecycle APIs.
6. Existing EP-ARCH-04.3 transaction ownership remains service-owned; this task adds the repository-side lifecycle guard without changing transaction policy.

## Audit result at baseline

The source audit for the requested baseline found no upward imports from repository modules into application services/presentation layers and no repository-side engine/session-factory construction. The implementation therefore adds regression protection rather than changing production behavior.

## Scope

- Source-driven AST regression coverage under `tests/test_ep_arch_04_7_dependency_direction_lifecycle.py`.
- Architecture documentation for the dependency-direction and session-lifecycle contract.

## Non-goals

- No business behavior changes.
- No repository query rewrite.
- No transaction-policy change.
- No Unit of Work introduction.
- No repository-to-repository refactor.
- No production repository implementation changes are required by the baseline audit.

## Relationship to previous contracts

- **EP-ARCH-04.1:** services use the RepositoryProvider boundary.
- **EP-ARCH-04.2:** RepositoryProvider remains complete and synchronized.
- **EP-ARCH-04.3:** transaction completion is service-owned.
- **EP-ARCH-04.4:** repository Session access remains encapsulated.
- **EP-ARCH-04.5:** consumers cannot recover repository/session escape hatches and repositories do not depend upward on services.
- **EP-ARCH-04.6:** repository APIs and explicit Session injection remain stable.
- **EP-ARCH-04.7:** repository dependency direction and Session/engine lifecycle ownership are now source-driven regression contracts.

## Validation

Run from `CenterManager`:

```powershell
pytest -q tests\test_ep_arch_04_7_dependency_direction_lifecycle.py
pytest -q tests\test_ep_arch_04_6_repository_api_contract.py
pytest -q
```
