# CenterManager — Database Design

Status: **CURRENT DATABASE ARCHITECTURE REFERENCE**  
Updated: 2026-09-24

This document describes the current database architecture and invariants. It intentionally does **not** maintain a hand-written exhaustive table list; SQLAlchemy models and Alembic migrations are the authoritative schema inventory.

## 1. Technology

CenterManager currently uses:

- SQLite as the runtime relational database;
- SQLAlchemy 2.x ORM;
- Alembic for schema evolution;
- repository abstractions for query/persistence access;
- application services for business/domain validation and transaction orchestration.

The old “8 Domain Tables” description is obsolete. The application now contains substantial Student, Class/Teaching, Employee/Teacher, Finance, Authorization/Admin, Audit/Timeline and platform-support persistence.

## 2. Sources of truth

For schema facts, use this order:

1. `src/centermanager/models/` — current ORM model definitions;
2. `migrations/versions/` — schema evolution/history;
3. repository contracts/tests — query and persistence behavior;
4. this document — architecture/invariants only.

Do not infer current schema from an old documentation table list.

## 3. Runtime database lifecycle

Database initialization is part of application bootstrap.

In configured Git collaboration mode, the synchronized Git repository state is authoritative and must be materialized before the production engine opens the runtime database. In true local/offline mode, the application can initialize a local runtime database.

After runtime DB materialization:

1. SQLAlchemy production engine/session factory are created;
2. Alembic upgrades the database to the current head;
3. authentication/application services begin normal data access.

A failed authoritative Git synchronization must not silently fall back to a stale local database.

## 4. Layer ownership

```text
UI
 ↓
Service / Policy / Read Model
 ↓
Repository Provider / Repository
 ↓
SQLAlchemy ORM
 ↓
SQLite
```

### Models

Define persisted state and relationships. Models are not the correct location for UI behavior or application orchestration.

### Repositories

Own query/persistence mechanics. Repositories may perform ORM selection, aggregation, add/delete/flush behavior and other persistence-specific operations according to their contracts.

### Services

Own application/domain validation, authorization orchestration and transaction use cases. Where repository ownership is established, services must not bypass it with direct ORM queries/persistence calls.

## 5. Transactions

Business operations that must succeed or fail together should use one database transaction.

Examples include:

- primary entity mutation plus its required audit/history row;
- Settlement confirmation snapshot plus status/audit state;
- Class fee mutation plus effective-dated fee-history persistence.

Post-commit projection/event work must not make an already committed transaction appear to have failed. Best-effort post-commit behavior must be explicit.

## 6. History and deletion

Historical preservation is domain-specific rather than a universal “never delete any row” rule.

Use the lifecycle defined by the owning domain/model/service:

- some entities use soft-delete/inactive states;
- some financial rows use explicit states such as ACTIVE/VOIDED or PENDING/COMPLETED;
- audit/timeline/history data is retained according to its domain contract;
- hard deletion is only allowed where the owning service/domain contract permits it.

Do not invent a global deletion rule that conflicts with an entity's lifecycle.

## 7. Finance persistence

Finance Wallet V2 is governed by:

`docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md`

Important current persistence concepts include:

- canonical `FinancePeriod` configuration/identity;
- Income and realized Expense canonical period assignment;
- `CASH` / `BANK` wallet semantics;
- Settlement confirmation/reopen lifecycle;
- effective-dated `ClassFeeHistory` for historical tuition obligations;
- unresolved historical data surfaced for explicit reconciliation rather than guessed/back-priced.

The Finance domain spec is authoritative over generic database guidance.

## 8. Effective-dated/history data

When a current configuration value would otherwise rewrite historical interpretation, use explicit effective-dated/history persistence when the domain requires it.

Example: Class tuition fee history records the effective fee source rather than using the latest `Class.fee` to recalculate old obligations.

Historical provenance matters. Migration/backfill rows should carry explicit provenance where interpretation could otherwise be ambiguous.

## 9. IDs and human identifiers

Integer primary keys are internal relational identities. Human-facing codes (for example student codes) remain domain identifiers/display values where defined by their models.

UI must not assume every entity uses the same identifier strategy; use DTO/service contracts.

## 10. Time and business date

Persisted timestamps follow model/database conventions. Business-date rules should use the application clock when the owning domain exposes one, rather than directly calling system time in multiple services.

Display formatting/localization belongs to projection/UI layers.

## 11. Foreign keys and referential integrity

SQLite foreign-key enforcement is enabled by the database layer. Migrations/models define referential behavior such as `RESTRICT`, cascades or nullable references according to each domain's lifecycle.

Do not add cascades merely for convenience; historical/accounting records often require restrictive deletion semantics.

## 12. Aggregation correctness

Financial and operational totals must be complete.

Do not implement totals by loading an arbitrary maximum number of rows such as `limit=100000`. Use database aggregation (`SUM`, `COUNT`, `GROUP BY`, etc.) when appropriate and prove high-volume behavior with tests when the domain is sensitive to truncation.

## 13. Migration strategy

Alembic is authoritative for schema evolution.

Rules:

- new schema changes use new forward migrations;
- inspect the current migration head/chain before creating a revision;
- preserve data by default;
- backfills must be deterministic;
- ambiguous legacy financial/domain data must become reconciliation exceptions rather than guessed assignments;
- do not rewrite an already-applied historical migration without an explicit release/migration reason;
- maintain migration-chain regression tests where present.

## 14. Test databases

Database tests must use isolated test fixtures/databases and must not mutate the user's production runtime database.

Architecture, migration, repository and service tests are part of the data-safety contract.

## 15. Files vs database

Structured business state belongs in SQLite unless a domain explicitly owns external file content.

Attachments, exports, documents and runtime/synchronization files use the filesystem through owning services/platform/path abstractions. Store references/metadata in the database where defined by the owning model.

Do not hard-code runtime filesystem locations in models or business logic.

## 16. Schema documentation rule

When a developer needs the exact current columns/indexes/constraints, inspect the ORM model and migration head. If a significant new persistence invariant is introduced, update this document's invariant sections rather than rebuilding a fragile manual table catalog.