# Phase 2 — Product Hardening

## Baseline

- Base commit: `4b44de8d9a0c463becdc979c3b8919b7026b5895`
- Branch: `phase-2-product-hardening`
- Scope: one consolidated hardening pass after EP-PROTOTYPE-13.

## Goals

This phase hardens the existing prototype without introducing a second architecture or redesigning the product. The implementation is contract-first and regression-gated.

### Domains covered

- Domain/data integrity
- Permission and mutation boundaries
- Error/recovery contracts
- Cross-workspace operational workflow consistency
- UX/error-state consistency at the code-contract level
- Reporting/export source-of-truth consistency
- Performance baseline contracts
- Backup/restore and deployment readiness

## Baseline findings

1. SQLite foreign-key enforcement is enabled at engine connection time.
2. Database schema is managed through Alembic and has an explicit head validation helper.
3. `session_scope()` owns commit/rollback/close behavior, while repositories remain caller-transaction-owned.
4. Student and Class domain models contain soft-delete fields, while several ORM relationships also use delete-orphan cascades. This means historical preservation must be enforced at service/mutation boundaries rather than inferred solely from ORM relationships.
5. Runtime paths already expose dedicated Backup, Logs, Config and Database directories, but backup/restore behavior must remain explicit and tested.
6. The prototype/application routing contract already has a single MainWindow routing owner and should not be duplicated.

## Hardening contract

### Data integrity

- Active lookup APIs must continue excluding soft-deleted primary records.
- Historical retrieval APIs must remain available for reporting/audit.
- Foreign keys remain enforced.
- Uniqueness constraints remain enforced by the database where already defined.
- Service-level validation must precede persistence for mutation rules that are not representable by database constraints.

### Transaction and recovery

- Every service mutation must have one explicit transaction owner.
- A failed mutation must rollback its transaction and must not leave partial persisted state.
- Repositories must not commit or rollback caller-owned transactions.
- Database refresh must dispose the old engine before creating the replacement session factory.

### Permissions

- UI visibility is not the authorization boundary.
- Mutation entry points must require the appropriate capability before persistence.
- Read-only and operational flows must remain reachable for authorized roles without creating bypass paths.

### Reporting/export

- Reports and exports must read through the established service/repository data paths rather than maintaining independent persistence state.
- Read-only export operations must not mutate the source database.

### Performance

- Do not add speculative caching or broad refactors in this phase.
- Establish source-level guardrails for bounded loading on high-volume operational surfaces.

### Backup/deployment

- Backup destinations must stay inside the dedicated runtime backup area or an explicitly supplied destination.
- Backup/restore operations must refresh database runtime state after replacing the database file.
- Runtime must be migratable to Alembic head before normal operation.

## Regression policy

Tests must be semantic/source-driven where appropriate and behavior-driven where a temporary database can prove the contract. No exact quote formatting, helper placement, or unrelated implementation detail may become a contract.
