# EP-SEC-01 — Database Lifecycle Protection

## Objective

Prevent the application from silently creating or accepting an empty local SQLite database when the expected runtime database is missing, corrupt, unreadable, or structurally empty.

## Security / data-integrity invariant

**Missing DB is not an empty DB.**

A runtime database is operational only when an existing SQLite file passes the lifecycle integrity checks. Any non-operational state requires recovery and must not be converted into a new empty database by SQLAlchemy or another database bootstrap path.

## Enforced contract

1. `DatabaseLifecycle` distinguishes `MISSING`, `CORRUPTED`, `UNREADABLE`, `INVALID_SCHEMA`, and `AVAILABLE`.
2. `create_engine_for_path()` opens SQLite using `mode=rw`, so SQLite cannot create a missing file as a side effect of connection.
3. Every engine connection validates the lifecycle state before the database is exposed to application code.
4. A missing database therefore remains missing; application code receives a recovery error instead of an empty database.
5. A SQLite file with no tables is treated as `INVALID_SCHEMA`, not as a valid empty database.
6. `RECOVERY_REQUIRED` is the normalized operational state for every non-available condition.

## Recovery boundary

The database engine does not invent or initialize business data. Recovery remains the responsibility of the higher-level authoritative flows already used by CenterManager, such as startup synchronization from the configured repository or explicit backup restore.

## Non-goals

This task does not implement database encryption, key management, backup encryption, or a full runtime UI for recovery. Those remain separate hardening work.

## Regression coverage

The EP-SEC-01 test contract verifies:

- missing database is rejected and is not materialized;
- an empty file is corrupted;
- a newly-created but schema-empty SQLite file is invalid;
- a valid SQLite database remains usable;
- a corrupt database enters the recovery-required contract.
