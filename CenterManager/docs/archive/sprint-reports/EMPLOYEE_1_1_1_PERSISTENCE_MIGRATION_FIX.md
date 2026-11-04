# EMPLOYEE 1.1.1 — Employee Persistence & Migration Contract Fix

## Objective
Fix the Employee persistence regression where creating an employee failed with:

`sqlite3.IntegrityError: NOT NULL constraint failed: employees.created_at`

## Root cause
`Employee` inherits `TimestampMixin`, whose ORM contract declares `created_at` and `updated_at` as database-generated server defaults. Migration `1e10a001` created both columns as `NOT NULL` but omitted the SQLite `CURRENT_TIMESTAMP` defaults. SQLAlchemy therefore omitted both values during INSERT while SQLite had no default to supply them.

## Changes

### New Alembic revision
- Revision: `1e10a003`
- Replaces the existing `employees` table columns using SQLite batch migration semantics.
- Adds database defaults for:
  - `created_at = CURRENT_TIMESTAMP`
  - `updated_at = CURRENT_TIMESTAMP`

The revision upgrades databases already at `1e10a002`; historical migrations are not rewritten.

### Employee model consistency
- Removed duplicate `unique=True` declarations from `employee_code` and `user_id`.
- Retained the explicit named `UniqueConstraint` definitions:
  - `uq_employee_code`
  - `uq_employee_user`

### Model registry
- Registered `EmployeeDocument` in `centermanager.models` and `__all__`.
- This ensures Alembic metadata and `Base.metadata` contain the Employee document table.

### Alembic configuration
- Restored root `alembic.ini`.
- Configured `script_location = migrations` and project import path.

### Regression coverage
Added tests for:
- Fresh migration to head includes `employees` and `employee_documents`.
- Existing database at `1e10a002` upgrades to the timestamp fix.
- Employee timestamp columns have database defaults.
- Direct Employee ORM insert succeeds after migration.
- `EmployeeService.create_employee()` succeeds and receives timestamps.
- `EmployeeDocument` is registered in `Base.metadata`.
- Full downgrade to base removes Employee tables.

## Verification

```text
python -m compileall -q src migrations tests
pytest -q tests/test_migrations.py tests/test_employee_persistence.py
```

Result: `6 passed`

## Migration chain

```text
5ce9314feb37 Initial Schema
        ↓
0ce070d8da89 Audit Trail
        ↓
1e10a001 Employee Foundation
        ↓
1e10a002 Employee Documents
        ↓
1e10a003 Employee Timestamp Defaults Fix
```
