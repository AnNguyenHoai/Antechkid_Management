# EP-ARCH-03 — Service Boundary Inventory

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

## EP-FIN-04 Financial Settlement

`FinancialSettlementService` is provider-backed and classified as `PASS`. It resolves FinancePeriod through `RepositoryProvider.finance_periods(...)`, reads Income/Expense through their repositories, and persists settlement snapshots through `RepositoryProvider.financial_settlements(...)`. The service owns business calculations and transaction completion; repositories own SQLAlchemy query/persistence operations.

## Inventory maintenance

Every new `*_service.py` must be added here in the same change. `LEGACY` remains a valid explicit status for future migration backlog; the `Next migration` column records that backlog when present.
