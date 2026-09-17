# EP-ARCH-03 — Service Boundary Inventory

Baseline: `a23ad673cdaea144244456b782371baf40914756`

## Contract

Application services are classified from their source AST:
- `PASS`: imports `RepositoryProvider` and has no concrete repository imports, repository construction, forbidden SQLAlchemy query imports, or direct persistence operations.
- `NON_REPOSITORY`: owns a non-database boundary and is not required to declare `RepositoryProvider`.
- `LEGACY`: database-backed service without `RepositoryProvider`; migration backlog.
- `VIOLATION`: declares `RepositoryProvider` but retains forbidden dependencies/operations.

The strict provider gate remains authoritative for every service that declares `RepositoryProvider`.

## Current inventory

| Service | Status | Repository imports | Repository constructors | SQLAlchemy imports | Direct persistence | Next migration |
|---|---|---|---|---|---|---|
| `assessment_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `attendance_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `audit_service.py` | PASS | — | — | — | repository-owned | — |
| `authorization_service.py` | NON_REPOSITORY | — | — | — | — | — |
| `auto_report_service.py` | NON_REPOSITORY | — | — | — | filesystem state file | — |
| `backup_operations_service.py` | NON_REPOSITORY | — | — | — | delegated to platform service | — |
| `class_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `class_timeline_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `configuration_service.py` | NON_REPOSITORY | — | — | — | configuration persistence | — |
| `employee_admin_management_service.py` | PASS | — | — | — | — | — |
| `employee_document_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `employee_schedule_service.py` | PASS | — | — | — | — | — |
| `employee_service.py` | PASS | — | — | — | — | — |
| `employee_work_registration_service.py` | PASS | — | — | — | — | — |
| `employee_working_time_service.py` | PASS | — | — | — | — | — |
| `enrollment_service.py` | PASS | — | — | — | repository-owned | — |
| `expense_service.py` | PASS | — | — | — | repository-owned | — |
| `expense_timeline_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `finance_dashboard_service.py` | NON_REPOSITORY | — | — | — | delegated to application services | — |
| `finance_period_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `git_config_service.py` | NON_REPOSITORY | — | — | — | encrypted filesystem config | — |
| `home_dashboard_service.py` | PASS | — | — | — | — | — |
| `income_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `outstanding_service.py` | PASS | — | — | — | repository-owned | — |
| `parent_service.py` | PASS | — | — | — | — | — |
| `permission_service.py` | PASS | — | — | — | — | — |
| `product_hardening_service.py` | NON_REPOSITORY | — | — | — | policy/path guards | — |
| `report_service.py` | PASS | — | — | — | repository-owned | — |
| `session_note_service.py` | PASS | — | — | — | — | — |
| `session_report_service.py` | PASS | — | — | — | — | — |
| `session_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_analytics_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_dashboard_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_document_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_export_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_filter_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_highlight_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_import_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_note_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_summary_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `system_operations_service.py` | NON_REPOSITORY | — | — | — | platform/filesystem health checks | — |
| `teacher_assignment_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `teacher_document_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `teacher_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `teacher_timeline_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `timeline_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |

## Inventory maintenance

This table is the committed architecture inventory and must be updated whenever a new `*_service.py` enters the application service tree. Non-database services must be classified as `NON_REPOSITORY` with their owned boundary stated explicitly.

## EP-ARCH-03.35 through Phase 2

The historical migration notes below remain authoritative for the completed repository-boundary migrations and Phase 2 hardening baseline.

- Provider-backed database services are `PASS`; database query/persistence remains repository-owned.
- Non-database orchestration services are `NON_REPOSITORY`; they are not migration backlog.
- Student, Session, Timeline, Expense, Teacher, Finance-period, import/export/note and related services remain covered by the completed migration slices.
- Phase 2 introduces `ProductHardeningService` as a small non-database cross-cutting guard for canonical authorization and managed filesystem paths; it does not own a database session or repository.

## Phase 2 hardening — ProductHardeningService
- `product_hardening_service.py` — **ProductHardeningService** is a cross-cutting non-database guard for canonical authorization and managed filesystem paths. It is classified as `NON_REPOSITORY` and does not own a database session or repository.

## EP-ARCH-03.35 Migration Rule

A service is only migrated into strict `PASS` when it has an application database repository boundary. Non-database responsibilities are `NON_REPOSITORY` and excluded from the RepositoryProvider requirement. Database-backed services without `RepositoryProvider` remain migration backlog until their own migration slice.
