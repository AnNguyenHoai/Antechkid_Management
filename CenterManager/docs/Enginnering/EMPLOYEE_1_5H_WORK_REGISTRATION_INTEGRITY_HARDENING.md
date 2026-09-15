# EMPLOYEE 1.5-H — Work Registration Integrity Hardening

## Business contract

Employee work registration is monthly availability input for manager planning. It is not official schedule and is not attendance.

Lifecycle: `DRAFT -> SUBMITTED -> CLOSED`.

## Changes

- Centralized permission checks through `PermissionService`; manager role name is no longer an authorization bypass.
- Block-level `submit()` is deprecated and rejected; monthly `submit_month()` is the only submission workflow.
- Added `EmployeeWorkRegistrationPeriod` with unique `(year, month)`, `OPEN/CLOSED` state, optional submission deadline, close timestamp and closer.
- Existing registration rows are backfilled into monthly periods by Alembic migration `1e10a010`.
- SQLite write mutations use `BEGIN IMMEDIATE` before overlap/status checks to serialize competing writers.
- A month cannot be closed while draft registrations remain, or when it has no registration blocks.
- Submitted/closed months cannot accept new availability blocks.
- Added audit events for create/update/delete/submit/deadline update/month close.
- Added canonical permission definitions for work registration.
- Employee Documents UI regression was preserved/fixed with an explicit Documents group.

## Compatibility

`APPROVED` and `REJECTED` status constants remain only for legacy database compatibility. New service flows do not create or transition to them.

## Verification

- Employee work registration tests: PASS.
- Employee/profile/access/document/migration focused suite: PASS.
- `python -m compileall -q src migrations tests`: PASS.
