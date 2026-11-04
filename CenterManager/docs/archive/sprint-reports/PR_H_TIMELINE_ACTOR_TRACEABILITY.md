# PR H — Unified Timeline Actor Attribution & History Traceability

## Goal

Every forward-going Timeline/History record should answer WHO performed the mutation.
Historical rows already persisted as system are not rewritten because their true actor cannot be reconstructed safely.

## Changes

- Adds a canonical timeline actor resolver: explicit actor -> authenticated username -> system.
- Student, Class, Teacher and Expense timeline services use the resolver centrally.
- Explicit background/system events remain explicitly attributed to system.
- Timeline cards display the stored actor alongside the event.
- Expense CREATE/UPDATE/DELETE now write actor-aware AuditLog rows in the same transaction as the mutation.
- ClassFeeHistory gains nullable changed_by for new fee versions through migration 1e10a039.

## Traceability invariant

Each human-facing mutation log should provide:
- WHO: created_by / actor_name
- WHAT: action/event type
- TARGET: entity identity
- WHEN: created_at
- DETAIL: description/metadata or audit details

## Historical data policy

No backfill guesses are made for existing timeline rows whose created_by is system.
No backfill guesses are made for existing class_fee_history rows; changed_by remains NULL for old rows.
