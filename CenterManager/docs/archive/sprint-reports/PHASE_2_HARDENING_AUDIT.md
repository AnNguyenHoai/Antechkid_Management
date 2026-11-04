# Phase 2 Hardening Audit

## Result

The prototype is retained as the product baseline. This audit does not introduce a second routing, repository, or authorization architecture.

### Verified existing contracts

- SQLite foreign keys are enabled for every engine connection.
- Transaction lifecycle is explicit and repositories do not own commit/rollback.
- Student and Class lifecycle operations use soft-delete/restore patterns.
- Authorization is centralized through `AuthorizationService` and canonical `Capability` identifiers.
- Backup payloads are validated with managed-path, SQLite integrity, manifest, and checksum checks.
- Release packaging excludes runtime databases and backups from shipped runtime content.
- Alembic head validation exists before normal database operation.

### Hardened in this phase

- Added a cross-cutting `ProductHardeningService` that reuses the canonical capability service and provides a managed-path guard without bypassing existing boundaries.
- Backup restore now refreshes the runtime SQLAlchemy session factory after database file replacement, preventing future sessions from remaining attached to the pre-restore engine.
- Added regression contracts covering data preservation, transaction boundaries, authorization vocabulary, backup integrity, restore refresh, and release packaging.

### Explicitly not changed

- No workspace redesign.
- No new persistence architecture.
- No new authorization vocabulary.
- No speculative caching layer.
- No business-rule changes not supported by an existing contract.
- No attempt to claim GUI UAT execution from source tests.

## Remaining manual/CI release gate

The following cannot be truthfully marked complete from repository inspection alone and must be executed against the branch:

1. Full pytest suite.
2. Manual desktop UAT for core golden flows.
3. Backup -> mutate -> restore -> reopen application verification.
4. Release packaging smoke test on the target Windows environment.
5. Large-dataset timing measurements for dashboard, student detail, class detail, timeline, and finance views.

These are release-gate executions, not deferred product architecture work.
