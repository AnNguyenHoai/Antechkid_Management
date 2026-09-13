# EP-ARCH-03 — Service Boundary Inventory

Baseline: `a23ad673cdaea144244456b782371baf40914756`

## Contract

Application services are classified from their source AST:

- `PASS`: imports `RepositoryProvider` and has no concrete repository imports, repository construction, forbidden SQLAlchemy query imports, or direct persistence operations.
- `NON_REPOSITORY`: service owns a non-database boundary such as authorization policy, filesystem configuration, backup/platform orchestration, or external collaboration operations. It is not required to declare `RepositoryProvider` because there is no application-repository boundary to migrate.
- `LEGACY`: database-backed application service does not yet declare `RepositoryProvider`; findings are migration backlog, not CI regressions until the service enters the strict gate.
- `VIOLATION`: declares `RepositoryProvider` but still has one or more forbidden dependencies/operations. This state must fail CI.

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
| `student_filter_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
| `student_highlight_service.py` | LEGACY | pending audit follow-up | pending audit follow-up | pending audit follow-up | pending audit follow-up | EP-ARCH-03.36 |
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

Batch A promotes already-provider-backed legacy services into the strict service-boundary inventory without changing their business behavior.

- `assessment_service.py` — **AssessmentService**: provider-backed assessment repository boundary; database persistence remains repository-owned.
- `attendance_service.py` — **AttendanceService**: provider-backed attendance, enrollment, and session repository boundary; database persistence remains repository-owned.

These services are `PASS` and are not migration backlog.

## EP-ARCH-03.35 Batch B

Batch B promotes already-provider-backed services into the strict service-boundary inventory.

- `audit_service.py` — **AuditService**: uses `RepositoryProvider` for audit repository operations; persistence remains repository-owned.
- `class_service.py` — **ClassService**: uses `RepositoryProvider` for class and related repository operations; persistence remains repository-owned.

These services are `PASS` and are not migration backlog.

## EP-ARCH-03.35 Batch D

Batch D promotes `EnrollmentService` into the strict provider-backed inventory.

- `enrollment_service.py` — **EnrollmentService**: uses `RepositoryProvider.enrollments(...)`; repository owns refresh/persistence operations while transaction ownership remains in the service.

`EnrollmentService` is `PASS` and is not migration backlog.

## EP-ARCH-03.35 Batch E

Batch E promotes `ClassTimelineService` into the strict provider-backed inventory.

- `class_timeline_service.py` — **ClassTimelineService**: uses `RepositoryProvider.class_timeline(...)`; repository owns add/refresh persistence operations while transaction ownership remains in the service. Database persistence is explicitly **repository-owned**.

These operations are repository-owned and `ClassTimelineService` is `PASS` and is not migration backlog.

## EP-ARCH-03.35 Batch F

Batch F promotes `EmployeeDocumentService` into the strict provider-backed inventory.

- `employee_document_service.py` — **EmployeeDocumentService**: uses `RepositoryProvider.employee_documents(...)`; repository owns database refresh/persistence operations while document filesystem behavior remains service-owned.

`EmployeeDocumentService` is `PASS` and is not migration backlog.

## EP-ARCH-03.35 Batch G

Batch G closes the false-positive legacy classification for services whose responsibilities are not database-repository backed. These services must not be forced to inject a `RepositoryProvider` merely to satisfy the service boundary gate.

- `authorization_service.py` — **AuthorizationService**: pure capability/policy decision logic; no database repository or persistence responsibility.
- `auto_report_service.py` — **AutoReportService**: orchestrates `StudentService` and `ReportService`; its only local persistence is a small JSON state file, which is intentionally filesystem-owned and not an application repository concern.
- `backup_operations_service.py` — **BackupOperationsService**: backup/platform orchestration delegated to the platform layer; no application repository dependency.
- `configuration_service.py` — **ConfigurationService**: validated configuration lifecycle using the configuration subsystem; no application repository dependency.
- `git_config_service.py` — **GitConfigService**: encrypted Git configuration stored in the configuration filesystem; Git connectivity is delegated to the platform Git provider.
- `system_operations_service.py` — **SystemOperationsService**: platform/filesystem health aggregation; direct SQLite health probing is diagnostic-only and is not application persistence.

These services are therefore `NON_REPOSITORY`, not migration backlog. Database-backed `LEGACY` services remain assigned to their dedicated migration batches.

## EP-ARCH-03.36-A StudentService

`StudentService` is now explicitly provider-backed through `RepositoryProvider.students(...)` and classified as `PASS`. Student persistence/query operations remain repository-owned, while the application service retains business validation, filesystem handling, transaction coordination, timeline orchestration, report-policy evaluation, and event publishing.

- `student_service.py` — **StudentService**: uses `RepositoryProvider.students(...)`; repository owns student query/persistence operations including refresh, while transaction completion remains service-owned.

## EP-ARCH-03.36-B Student read/presentation services

Batch B migrates the remaining Student-domain read/summary application services that still performed database access directly.

- `student_analytics_service.py` — **StudentAnalyticsService**: uses `RepositoryProvider.students(...)` and `RepositoryProvider.assessments(...)`; analytics aggregation remains service-owned while database reads remain repository-owned.
- `student_dashboard_service.py` — **StudentDashboardService**: uses `RepositoryProvider.students(...)`, `assessments(...)`, `parents(...)`, `sessions(...)`, and `class_timeline(...)`; dashboard DTO aggregation and filtering remain service-owned while database reads remain repository-owned.
- `student_summary_service.py` — **StudentSummaryService**: composes existing Student/Parent/Assessment/Timeline services and uses `RepositoryProvider.documents(...)` for its document read; no concrete repository construction remains in the service.

All three services are now `PASS`. Their public behavior and DTO shapes remain unchanged; the migration only moves database access behind the provider boundary. `RepositoryProvider.documents(...)` is now part of the application repository contract for this purpose.

The remaining Student-domain legacy services stay assigned to EP-ARCH-03.36 for later migration slices.

## EP-ARCH-03.36-C Student document boundary

Batch C migrates `StudentDocumentService`, which has both a database-backed Document lifecycle and a filesystem attachment boundary.

- `student_document_service.py` — **StudentDocumentService**: uses `RepositoryProvider.documents(...)` for document persistence and reads; `DocumentRepository` is no longer imported or constructed by the service.
- Database `add`, `delete`, and `refresh` operations remain repository-owned; transaction completion remains service-owned.
- Attachment directory creation, file copy, and file deletion remain explicitly filesystem-owned by the service and are not disguised as repository operations.
- Database repository behavior remains repository-owned; filesystem behavior remains service-owned.

`StudentDocumentService` is now `PASS` and is not migration backlog. The migration preserves its existing public API and document/timeline behavior while normalizing the database dependency boundary.

The remaining Student-domain legacy services stay assigned to EP-ARCH-03.36 for later migration slices.

## EP-ARCH-03.35 Migration Rule

A service is only migrated into the strict `PASS` class when it has an application database repository boundary. Non-database responsibilities are explicitly classified as `NON_REPOSITORY` and are excluded from the RepositoryProvider requirement.

Any service that is database-backed and does not yet declare `RepositoryProvider` remains in the migration backlog until its own migration slice is implemented.
