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
| `expense_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `expense_timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `finance_dashboard_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `finance_period_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `git_config_service.py` | NON_REPOSITORY | — | — | — | encrypted filesystem config | — |
| `home_dashboard_service.py` | PASS | — | — | — | — | — |
| `income_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `outstanding_service.py` | PASS | — | — | — | repository-owned | — |
| `parent_service.py` | PASS | — | — | — | — | — |
| `permission_service.py` | PASS | — | — | — | — | — |
| `report_service.py` | PASS | — | — | — | repository-owned | — |
| `session_note_service.py` | PASS | — | — | — | — | — |
| `session_report_service.py` | PASS | — | — | — | — | — |
| `session_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.37 |
| `student_analytics_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_dashboard_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_document_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_export_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_filter_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_highlight_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_import_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_note_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `student_summary_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `system_operations_service.py` | NON_REPOSITORY | — | — | — | platform/filesystem health checks | — |
| `teacher_assignment_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `teacher_document_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `teacher_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `teacher_timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.37 |

## EP-FIN-01 FinancePeriodService
- `finance_period_service.py` — **FinancePeriodService**: uses `RepositoryProvider.finance_periods(...)`; period persistence/query operations remain repository-owned while Admin authorization and period business rules remain service-owned.
- The service is classified as `PASS` and is not migration backlog.

## EP-ARCH-03 Migration Rule
A service is only migrated into strict `PASS` when it has an application database repository boundary. Non-database responsibilities are `NON_REPOSITORY` and excluded from the RepositoryProvider requirement. Database-backed services without `RepositoryProvider` remain migration backlog until their own migration slice.
