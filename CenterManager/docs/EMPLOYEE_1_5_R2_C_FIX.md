# EMPLOYEE 1.5-R2-C-FIX — Monthly Registration Schema Reconciliation

## Purpose

Reconcile the SQLite schema with the R2-C monthly work-registration aggregate model.

## Root Cause

Revisions `1e10a011` and `1e10a012` migrated availability details into
`employee_work_registration_blocks` but intentionally retained the legacy
`work_date`, `start_time`, `end_time`, `work_type`, `notes`,
`created_by_user_id`, and `reviewed_by_user_id` columns on
`employee_work_registrations`.

Those legacy columns include NOT NULL fields. R2-C application code creates a
monthly aggregate using only `employee_id`, `period_id`, status and lifecycle
metadata, so SQLite rejects a new aggregate with a NOT NULL constraint error.

## Fix

Migration `1e10a013_reconcile_monthly_registration_schema` rebuilds
`employee_work_registrations` to the canonical aggregate schema while
preserving existing registration IDs and lifecycle data.

Canonical aggregate fields:

- `id`
- `employee_id`
- `period_id`
- `status`
- `submitted_at`
- `accepted_at`
- `accepted_by_user_id`
- `created_at`
- `updated_at`

Availability detail remains in `employee_work_registration_blocks`.

## Safety Checks

The migration refuses to proceed when:

- a registration has `NULL period_id`;
- a registration references a missing period;
- duplicate `(employee_id, period_id)` aggregate roots remain;
- a block references a missing registration;
- an unexpected leftover temporary table exists.

After replacement it verifies that legacy block columns are gone and block
references still resolve.

## Validation

`tests/test_employee_work_registration_schema_migration.py` covers:

1. successful schema reconciliation and data preservation;
2. rejection of NULL `period_id` data before schema change;
3. rejection of orphan availability blocks before schema change.

## Scope

No R2-C service/UI behavior is changed. The fix is limited to database schema
reconciliation and migration coverage.
