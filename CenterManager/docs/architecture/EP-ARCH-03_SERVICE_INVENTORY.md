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
| `income_service.py` | PASS | — | — | `sqlalchemy.orm` only | repository-owned | — |
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

## EP-ARCH-03.35 Batch A
- `assessment_service.py` — **AssessmentService**: provider-backed assessment repository boundary; persistence remains repository-owned.
- `attendance_service.py` — **AttendanceService**: provider-backed attendance/enrollment/session repository boundary; persistence remains repository-owned.

## EP-ARCH-03.35 Batch B
- `audit_service.py` — **AuditService**: uses `RepositoryProvider`; persistence remains repository-owned.
- `class_service.py` — **ClassService**: uses `RepositoryProvider`; persistence remains repository-owned.

## EP-ARCH-03.35 Batch D
- `enrollment_service.py` — **EnrollmentService**: uses `RepositoryProvider.enrollments(...)`; repository owns refresh/persistence and service owns transaction completion.

## EP-ARCH-03.35 Batch E
- `class_timeline_service.py` — **ClassTimelineService**: uses `RepositoryProvider.class_timeline(...)`; repository owns persistence. Database persistence is explicitly **repository-owned**.

## EP-ARCH-03.35 Batch F
- `employee_document_service.py` — **EmployeeDocumentService**: uses `RepositoryProvider.employee_documents(...)`; repository owns database operations while document filesystem behavior remains service-owned.

## EP-ARCH-03.35 Batch G
Batch G closes the false-positive legacy classification for non-database services. These services must not be forced to inject a `RepositoryProvider`.
- `authorization_service.py` — **AuthorizationService**: pure capability/policy logic.
- `auto_report_service.py` — **AutoReportService**: orchestrates existing services; local JSON state is filesystem-owned.
- `backup_operations_service.py` — **BackupOperationsService**: platform orchestration.
- `configuration_service.py` — **ConfigurationService**: configuration subsystem.
- `git_config_service.py` — **GitConfigService**: encrypted filesystem configuration and platform Git provider.
- `system_operations_service.py` — **SystemOperationsService**: platform/filesystem health aggregation.

## EP-ARCH-03.36-A StudentService
`StudentService` — **StudentService** is explicitly provider-backed through `RepositoryProvider.students(...)` and classified as `PASS`. Student query/persistence operations remain repository-owned while business validation, transaction coordination, timeline/report/event orchestration remain service-owned.

## EP-ARCH-03.36-B Student read/presentation services
- `student_analytics_service.py` — **StudentAnalyticsService**: `RepositoryProvider.students(...)` and `assessments(...)`; aggregation remains service-owned.
- `student_dashboard_service.py` — **StudentDashboardService**: provider-backed student/assessment/parent/session/timeline reads; DTO aggregation remains service-owned.
- `student_summary_service.py` — **StudentSummaryService**: uses `RepositoryProvider.documents(...)` and existing domain services.

All three are `PASS`; database reads remain repository-owned.

## EP-ARCH-03.36-C Student document boundary
`StudentDocumentService` has both database and filesystem responsibilities.
- `student_document_service.py` — **StudentDocumentService**: uses `RepositoryProvider.documents(...)`; database add/delete/refresh are repository-owned and transaction completion is service-owned.
- Attachment directory creation, file copy, and file deletion remain explicitly filesystem-owned by the service.
- `filesystem behavior remains service-owned`.

`StudentDocumentService` is `PASS` and is not migration backlog.

## EP-ARCH-03.36-D Student filter/highlight boundary
Batch D migrates the Student filtering and highlight application services behind the repository boundary.
- `student_filter_service.py` — **StudentFilterService**: uses `RepositoryProvider.students(...)`; database-backed filtering is repository-owned while age calculation remains service-owned.
- `student_highlight_service.py` — **StudentHighlightService**: uses `RepositoryProvider.student_highlights(...)`; repository owns highlight query/add/delete/refresh operations while validation, transaction coordination, and event publishing remain service-owned.

Both services are `PASS` and are not migration backlog. Database persistence/query behavior is repository-owned.

## EP-FIN-01 FinancePeriodService
- `finance_period_service.py` — **FinancePeriodService**: uses `RepositoryProvider.finance_periods(...)`; period persistence/query operations remain repository-owned while Admin authorization and period business rules remain service-owned.
- The service is classified as `PASS` and is not migration backlog.

## EP-FIN-02 Period-aware Income & Outstanding
- `income_service.py` — **IncomeService** is now provider-backed through `RepositoryProvider.incomes(...)` and allocates every newly created/updated income to the canonical Finance period bucket derived from its payment date.
- `outstanding_service.py` — **OutstandingService** resolves the configured Finance period, filters enrollments by period/class/course/student, and calculates Tuition paid only within that period.
- `IncomeRepository` owns period-aware income filtering; `EnrollmentRepository` owns period/course/student filtering.
- Outstanding statuses are explicitly `Not Yet`, `Partial`, `Paid`, `Overpaid`, or `No Tuition Configured`.

## EP-ARCH-03.35 Migration Rule
A service is only migrated into strict `PASS` when it has an application database repository boundary. Non-database responsibilities are `NON_REPOSITORY` and excluded from the RepositoryProvider requirement. Database-backed services without `RepositoryProvider` remain migration backlog until their own migration slice.
