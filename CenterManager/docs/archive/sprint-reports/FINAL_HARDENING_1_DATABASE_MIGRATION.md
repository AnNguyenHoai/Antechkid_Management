# FINAL HARDENING 1 — Database Migration Foundation

## Goal
Replace runtime `Base.metadata.create_all()` and one-off `ALTER TABLE` startup patches with Alembic as the single schema evolution mechanism.

## Runtime lifecycle
1. Startup synchronization obtains the runtime database.
2. `ensure_schema()` calls `upgrade_database_to_head()`.
3. A new database upgrades from Alembic `base` to `head`.
4. A legacy database without `alembic_version` is stamped at the historical baseline only when it already contains the legacy core schema.
5. Alembic then upgrades it to `head`.

## Current revisions
- `5ce9314feb37` — historical initial schema
- `0ce070d8da89` — audit trail schema additions

## Rule for future development
Every persistent model/schema change must be accompanied by an Alembic revision. Do not add startup `create_all()` or ad-hoc `ALTER TABLE` patches.
