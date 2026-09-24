# EP-ARCH-03 — Service Boundary Inventory

Baseline: `a23ad673cdaea144244456b782371baf40914756`

This inventory is the committed architecture classification for application services.

## Contract

- `PASS`: provider-backed database service; query/persistence operations are repository-owned.
- `NON_REPOSITORY`: service owns a non-database boundary or delegates to application services.
- `LEGACY`: database-backed service awaiting repository migration.
- `VIOLATION`: provider-backed service that still leaks direct persistence/query operations.

## Current inventory

| Service | Status | Persistence boundary | Next migration |
|---|---|---|---|
| `assessment_service.py` | PASS | repository-owned | — |
| `attendance_service.py` | PASS | repository-owned | — |
| `audit_service.py` | PASS | repository-owned | — |
| `authorization_service.py` | NON_REPOSITORY | policy logic | — |
| `auto_report_service.py` | NON_REPOSITORY | filesystem/orchestration | — |
| `backup_operations_service.py` | NON_REPOSITORY | platform delegation | — |
| `class_service.py` | PASS | repository-owned | — |
| `class_timeline_service.py` | PASS | repository-owned | — |
| `configuration_service.py` | NON_REPOSITORY | configuration subsystem | — |
| `employee_admin_management_service.py` | PASS | repository-owned | — |
| `employee_document_service.py` | PASS | repository-owned + service-owned filesystem | — |
| `employee_schedule_service.py` | PASS | repository-owned | — |
| `employee_service.py` | PASS | repository-owned | — |
| `employee_work_registration_service.py` | PASS | repository-owned | — |
| `employee_working_time_service.py` | PASS | repository-owned | — |
| `enrollment_service.py` | PASS | repository-owned | — |
| `expense_service.py` | PASS | repository-owned | — |
| `expense_timeline_service.py` | PASS | repository-owned | — |
| `finance_dashboard_service.py` | NON_REPOSITORY | application-service aggregation | — |
| `finance_period_service.py` | PASS | repository-owned | — |
| `financial_settlement_service.py` | PASS | `RepositoryProvider.financial_settlements/finance_periods/incomes/expenses` | — |
| `git_config_service.py` | NON_REPOSITORY | encrypted filesystem config | — |
| `home_dashboard_service.py` | PASS | repository-owned | — |
| `income_service.py` | PASS | repository-owned | — |
| `outstanding_service.py` | PASS | repository-owned | — |
| `parent_service.py` | PASS | repository-owned | — |
| `permission_service.py` | PASS | repository-owned | — |
| `product_hardening_service.py` | NON_REPOSITORY | policy/path guards | — |
| `report_service.py` | PASS | repository-owned | — |
| `session_note_service.py` | PASS | repository-owned | — |
| `session_report_service.py` | PASS | repository-owned | — |
| `session_service.py` | PASS | repository-owned | — |
| `student_analytics_service.py` | PASS | repository-owned | — |
| `student_dashboard_service.py` | PASS | repository-owned | — |
| `student_document_service.py` | PASS | repository-owned + service-owned filesystem | — |
| `student_export_service.py` | PASS | repository-owned + service-owned export | — |
| `student_filter_service.py` | PASS | repository-owned | — |
| `student_highlight_service.py` | PASS | repository-owned | — |
| `student_import_service.py` | PASS | repository-owned + service-owned import parsing | — |
| `student_note_service.py` | PASS | repository-owned | — |
| `student_service.py` | PASS | repository-owned | — |
| `student_summary_service.py` | PASS | repository-owned | — |
| `system_operations_service.py` | NON_REPOSITORY | platform/filesystem health | — |
| `teacher_assignment_service.py` | PASS | repository-owned | — |
| `teacher_document_service.py` | PASS | repository-owned + service-owned filesystem | — |
| `teacher_service.py` | PASS | repository-owned | — |
| `teacher_timeline_service.py` | PASS | repository-owned | — |
| `timeline_service.py` | PASS | repository-owned | — |
| `wallet_service.py` | PASS | repository-owned aggregation through `RepositoryProvider.incomes/expenses` | — |

## EP-FIN-04 Financial Settlement

`financial_settlement_service.py` — **FinancialSettlementService** is provider-backed and classified as `PASS`. It resolves FinancePeriod through `RepositoryProvider.finance_periods(...)`, reads Income/Expense through `RepositoryProvider.incomes(...)` and `RepositoryProvider.expenses(...)`, and persists settlement snapshots through `RepositoryProvider.financial_settlements(...)`. The service owns reconciliation calculations, authorization and transaction completion; repositories own SQLAlchemy query/persistence operations.

## FW2-06 Wallet Accounting

`wallet_service.py` — **WalletService** is provider-backed and classified as `PASS`. It composes repository-owned grouped Income/Expense aggregates into the canonical `CASH`/`BANK` read model. Wallet alias resolution, balance equations and DTO projection are service-owned; SQL queries and persistence remain repository-owned.

## Inventory maintenance

Every new `*_service.py` must be added here in the same change. `LEGACY` remains a valid explicit status for future migration backlog; the `Next migration` column records that backlog when present.

## EP-ARCH-03.35 through Phase 2

The historical migration notes below remain authoritative for the completed repository-boundary migrations and Phase 2 hardening baseline.

- Provider-backed database services are `PASS`; database query/persistence remains repository-owned.
- Non-database orchestration services are `NON_REPOSITORY`; they are not migration backlog.
- Student, Session, Timeline, Expense, Teacher, Finance-period, import/export/note and related services remain covered by the completed migration slices.
- Phase 2 introduces `ProductHardeningService` as a small non-database cross-cutting guard for canonical authorization and managed filesystem paths; it does not own a database session or repository.

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
- `finance_dashboard_service.py` — **FinanceDashboardService**: read-only application-level aggregation/orchestration over provider-backed finance services; no database session, repository construction, SQLAlchemy query, or persistence boundary.
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

## EP-ARCH-03.37 Session/Timeline repository boundary
- `session_service.py` — **SessionService** uses `RepositoryProvider.sessions(...)` and `RepositoryProvider.classes(...)`; validation, authorization, transaction completion, timeline orchestration, and event publishing remain service-owned while session/class persistence/query operations remain repository-owned.
- `timeline_service.py` — **TimelineService** uses `RepositoryProvider.timeline(...)`; event construction/serialization remains service-owned while timeline persistence/query/refresh operations remain repository-owned.
- Both services are promoted to `PASS`; no concrete repository construction or direct session persistence/query operation remains in the application-service layer.

## EP-ARCH-03.38 Expense repository boundary
- `expense_service.py` — **ExpenseService** uses `RepositoryProvider.expenses(...)`; validation, authorization, transaction completion, and expense timeline orchestration remain service-owned while database persistence/query operations remain repository-owned.
- `expense_timeline_service.py` — **ExpenseTimelineService** uses `RepositoryProvider.expense_timeline(...)`; event construction/serialization remains service-owned while database persistence and refresh are repository-owned.
- Both services are promoted to `PASS`; no concrete repository construction or direct session persistence/query operation remains in the application-service layer.

## EP-ARCH-03.38 Finance Dashboard boundary
`FinanceDashboardService` is a read-only application-level aggregation/orchestration service. It does not own a database session, construct repositories, execute SQLAlchemy queries, or perform persistence. It composes the already provider-backed `IncomeService`, `ExpenseService`, and `OutstandingService` APIs. Therefore it is explicitly classified as `NON_REPOSITORY`, not `PASS` or `LEGACY`.

This classification closes the EP-ARCH-03.38 Finance Dashboard audit without introducing a redundant repository layer or duplicating finance query logic in the dashboard service.

## EP-ARCH-03.39 Teacher services repository boundary
- `teacher_service.py` — **TeacherService** uses `RepositoryProvider.teachers(...)`; teacher CRUD, search, archive/restore, and relation reads remain repository-backed while validation, transaction coordination, timeline orchestration, and event publishing remain service-owned.
- `teacher_assignment_service.py` — **TeacherAssignmentService** uses `RepositoryProvider.teacher_assignments(...)`, `teachers(...)`, and `classes(...)`; assignment persistence and lookup remain repository-owned while validation, transaction coordination, timeline orchestration, and event publishing remain service-owned.
- `teacher_document_service.py` — **TeacherDocumentService** uses `RepositoryProvider.teacher_documents(...)` and `teachers(...)`; database persistence/query operations remain repository-owned while attachment filesystem operations and compensation/cleanup remain service-owned.
- `teacher_timeline_service.py` — **TeacherTimelineService** uses `RepositoryProvider.teacher_timeline(...)`; timeline persistence/query/refresh operations remain repository-owned while event construction/serialization remains service-owned.

All four Teacher services are promoted to `PASS`. No concrete repository construction or direct session persistence/query operation remains in the application-service layer.

## Phase 2 — Architecture Hardening
The first Phase 2 hardening slice closes stale architecture classification for the Student export/import/note services.
- `student_export_service.py` — **StudentExportService** is provider-backed through `RepositoryProvider.students(...)`; student reads remain repository-owned while Excel/CSV generation remains service-owned.
- `student_import_service.py` — **StudentImportService** is provider-backed through `RepositoryProvider.students(...)`; duplicate-code lookup remains repository-owned while workbook parsing, validation delegation, and import orchestration remain service-owned.
- `student_note_service.py` — **StudentNoteService** is provider-backed through `RepositoryProvider.notes(...)`; note persistence/refresh/query remain repository-owned while validation and timeline orchestration remain service-owned.

All three are now `PASS`. They are not migration backlog.

## Phase 2 hardening — ProductHardeningService
- `product_hardening_service.py` — **ProductHardeningService** is a cross-cutting non-database guard for canonical authorization and managed filesystem paths. It is classified as `NON_REPOSITORY` and does not own a database session or repository.

## EP-ARCH-03.35 Migration Rule

A service is only migrated into strict `PASS` when it has an application database repository boundary. Non-database responsibilities are `NON_REPOSITORY` and excluded from the RepositoryProvider requirement. Database-backed services without `RepositoryProvider` remain migration backlog until their own migration slice.
