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
| `enrollment_transfer_service.py` | PASS | repository-owned | — |
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
| `tuition_accrual_service.py` | PASS | repository-owned | — |
| `tuition_adjustment_service.py` | PASS | repository-owned adjustment/Income orchestration | — |
| `tuition_detail_service.py` | PASS | repository-owned read model | — |
| `wallet_service.py` | PASS | repository-owned aggregation through `RepositoryProvider.incomes/expenses` | — |

## TUITION-13 Enrollment Transfer

`enrollment_transfer_service.py` is provider-backed and classified as `PASS`. It coordinates source/target Enrollment contracts, transfer-ledger persistence, tuition settlement reads and audit recording through `RepositoryProvider`; repositories own database query/persistence operations while transfer validation and transaction completion remain service-owned.

## TUITION-16 Tuition Adjustment Ledger

`tuition_adjustment_service.py` is provider-backed and classified as `PASS`. It coordinates first-class refund/credit adjustment policy, transaction completion, audit and event publication through `RepositoryProvider.tuition_adjustments/incomes/enrollments/finance_periods/sessions`. SQLAlchemy query and persistence behavior, including row-lock acquisition and aggregate reads, remains repository-owned. Accounting-date mutability is crossed only through `FinanceLedgerGuard`.

`tuition_refund.py` is a compatibility adapter, not an additional persistence boundary: legacy callers delegate to `TuitionAdjustmentService`, preventing a second refund path that could bypass the adjustment ledger.

## Key finance boundaries

- `financial_settlement_service.py`: provider-backed settlement reconciliation; persistence stays in financial-settlement, period, income and expense repositories.
- `income_service.py`: provider-backed Income lifecycle and period-aware Income persistence.
- `outstanding_service.py`: provider-backed tuition outstanding read model.
- `wallet_service.py`: provider-backed CASH/BANK aggregation over canonical Income/Expense records.
- `tuition_adjustment_service.py`: provider-backed tuition adjustment orchestration; non-cash credits are projected to tuition settlement through repository-owned queries and do not create wallet Income.

## Inventory maintenance

Every new `*_service.py` must be added here in the same change. `LEGACY` remains a valid explicit status for future migration backlog; the `Next migration` column records that backlog when present.

## Architecture rules retained from EP-ARCH-03 migration

- Provider-backed database services are `PASS`; database query/persistence remains repository-owned.
- Non-database orchestration services are `NON_REPOSITORY`; they are not migration backlog.
- Services may own validation, authorization, transaction coordination, DTO projection, audit/event orchestration and filesystem behavior where explicitly classified.
- Repositories own SQLAlchemy query/add/delete/refresh/locking behavior.
- Cross-domain accounting state is accessed through the established finance guard/provider boundaries rather than importing accounting models into tuition services.
