# EP-ARCH-03 — Service Boundary Inventory

Baseline: `a23ad673cdaea144244456b782371baf40914756`

## Contract

Application services are classified from their source AST:

- `PASS`: imports `RepositoryProvider` and has no concrete repository imports, repository construction, forbidden SQLAlchemy query imports, or direct persistence operations.
- `LEGACY`: does not yet declare `RepositoryProvider`; findings are migration backlog, not CI regressions until the service enters the strict gate.
- `VIOLATION`: declares `RepositoryProvider` but still has one or more forbidden dependencies/operations. This state must fail CI.

The strict provider gate remains authoritative for every service that declares `RepositoryProvider`.

## Current inventory

| Service | Status | Repository imports | Repository constructors | SQLAlchemy imports | Direct persistence | Next migration |
|---|---|---|---|---|---|---|
| `assessment_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `attendance_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
| `audit_service.py` | LEGACY | already provider-backed; not yet promoted | — | — | — | EP-ARCH-03.35 |
| `authorization_service.py` | LEGACY | no repository boundary | — | — | — | EP-ARCH-03.35 |
| `auto_report_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.35 |
| `backup_operations_service.py` | LEGACY | no concrete repository dependency | — | — | delegated to platform service | EP-ARCH-03.35 |
| `class_service.py` | LEGACY | already provider-backed; strict promotion deferred to class boundary slice | — | `sqlalchemy.orm` only | repository-owned | EP-ARCH-03.35 |
| `class_timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.35 |
| `configuration_service.py` | LEGACY | no repository boundary | — | — | configuration persistence | EP-ARCH-03.35 |
| `employee_admin_management_service.py` | PASS | — | — | — | — | — |
| `employee_document_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.35 |
| `employee_schedule_service.py` | PASS | — | — | — | — | — |
| `employee_service.py` | PASS | — | — | — | — | — |
| `employee_work_registration_service.py` | PASS | — | — | — | — | — |
| `employee_working_time_service.py` | PASS | — | — | — | — | — |
| `enrollment_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.35 |
| `expense_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `expense_timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `finance_dashboard_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `git_config_service.py` | LEGACY | no repository boundary | — | — | filesystem persistence | EP-ARCH-03.35 |
| `home_dashboard_service.py` | PASS | — | — | — | — | — |
| `income_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.38 |
| `outstanding_service.py` | PASS | — | — | — | — | — |
| `parent_service.py` | PASS | — | — | — | — | — |
| `permission_service.py` | PASS | — | — | — | — | — |
| `report_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.35 |
| `session_note_service.py` | PASS | — | — | — | — | — |
| `session_report_service.py` | PASS | — | — | — | — | — |
| `session_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.37 |
| `student_analytics_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_dashboard_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_document_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_export_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_filter_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_highlight_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_import_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_note_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_summary_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `system_operations_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.35 |
| `teacher_assignment_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `teacher_document_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `teacher_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `teacher_timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.39 |
| `timeline_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.37 |

## EP-ARCH-03.35 Batch A

Batch A promotes the following provider-backed services into the strict inventory:

- `assessment_service.py` — **AssessmentService**: provider-backed through `RepositoryProvider.assessments(...)`; repository operations are already isolated behind `AssessmentRepository`.
- `attendance_service.py` — **AttendanceService**: provider-backed through `RepositoryProvider.attendance(...)`, `sessions(...)`, and `enrollments(...)`; no direct SQLAlchemy persistence/query operations remain in the service.

These two services therefore move to `PASS` without production logic changes. Remaining legacy services keep their migration slice assignments above.
