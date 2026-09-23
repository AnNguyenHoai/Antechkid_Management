# UI-PROD-08 — Student Workspace Migration

## Baseline and scope

- Base: `main_repos@a633616e4ab5da248b643e990f3d5ee67b745e4f`.
- Prerequisite: UI-PROD-07 Feedback & State UX is merged.
- Scope: Student Workspace only. Other workspaces are intentionally unchanged.

### Scope supersession

This final UI-PROD-08 scope **supersedes** earlier planning copy in UI-PROD-06/UI-PROD-07 that described UI-PROD-08 as the migration task for every operational workspace. The implemented and accepted UI-PROD-08 vertical slice is Student-only.

Teacher, Class, Finance, Employee and Admin page-body migrations are not implied to be complete by UI-PROD-08 or UI-PROD-10. They belong to a later workspace-migration wave and may reuse the Design System V2, shell, data-heavy, form/detail and feedback contracts established here.

## Goal

Move the Student operational journey from mixed legacy presentation to Design System V2 and the UI-PROD-07 feedback/state contracts without changing Student domain ownership or service APIs.

## Migration matrix

| Surface | UI-PROD-08 contract |
| --- | --- |
| Student shell | Reuse the application-level `FeedbackController`/`FeedbackHost`; keep background synchronization passive. |
| Student list | `SearchToolbar` + `DataTable` + `BulkActionBar`, no-result/loading/error states, `EditStateBanner`, safe confirmations. |
| Student form | V2 fields and inline validation; `Save → Saving… → Student saved ✓`; readable save errors. |
| Student detail | `Tabs`, empty/error states, V2 toolbar, `EditStateBanner`, token-driven detail sections. |
| Profile | Preserve existing Profile, Summary, Parent, Assessment, Timeline, Notes and Documents business widgets. |
| Enrollment | V2 cards/select/buttons/badges, explicit transition confirmation, readable feedback, read-only projection. |
| Attendance | Read-only V2 `DataTable` with loading/empty/error states. |
| Finance context | Read-only Finance projection with `PermissionState`, V2 tables/cards and existing `finance.view` permission. |
| Analytics | Preserve analytics service/charts; route errors and export-placeholder feedback through the shared feedback contract. |
| Dashboard | Preserve existing dashboard behavior and service contract. |

## Interaction contracts

### Save

Student create/edit follows UI-PROD-07: user presses Save, the shared controller enters `Saving…`, duplicate submit is guarded, validation stays inline, success publishes `Student saved ✓`, and unexpected errors are logged while the UI receives readable copy.

### Destructive actions

Delete, bulk delete, parent delete and enrollment withdrawal use `ConfirmationDialog`. Destructive confirmations keep Cancel as the safe keyboard default.

### Read-only/edit mode

Student List, Detail and Enrollment reuse the UI-PROD-06 `EditStateBanner` contract. Search, filter, refresh, export, attendance viewing and permitted Finance viewing remain read-only operations.

### Content states

- List loading/error is owned by `DataTable`.
- Search/filter no-match uses `EmptySearchState`.
- Student Detail has explicit select-a-student and recoverable error states.
- Finance denial uses `PermissionState` rather than a technical error.
- Attendance and Finance tables use shared loading/empty/error patterns.

### Feedback ownership and retry routing

There is one visible application feedback host: `ApplicationTopBar.feedback_host`. Student Workspace binds List, Detail, Enrollment, Attendance, Finance context and Analytics to the application feedback controller after it is attached to MainWindow.

Retry actions are routed back to their owning surfaces:

- `student-list-refresh`
- `student-detail-refresh`
- `student-enrollment-refresh`
- `student-attendance-refresh`
- `student-analytics-refresh`

Background synchronization remains passive: synchronization events refresh Student data but do not publish success notifications.

## Business boundaries preserved

UI-PROD-08 is a presentation migration, not a domain rewrite.

- Student, Parent, Enrollment, Attendance, Assessment, Timeline, Report and related service APIs remain unchanged.
- Finance continues to own money. Student Finance consumes `OutstandingService`, `IncomeService` and `FinancePeriodService` read APIs only.
- `finance.view` remains the authorization boundary.
- Collaboration/WRITE mode remains the mutation guard; UI state supplements rather than replaces service-side protection.
- Existing Student signals and workspace navigation contracts remain intact.

## Definition of done

- Student operational journey uses Design System V2 primitives for list/form/detail/tabs/enrollment/attendance/finance context.
- UI-PROD-07 feedback controller/host is shared rather than duplicated.
- Save, confirmation, read-only, permission, loading, empty/no-result and error states follow shared contracts.
- Student finance remains read-only and permission-aware.
- Background sync remains passive.
- No Student service/domain API changes are required.
- Regression tests protect the migration architecture and prevent core surfaces from regressing to `QMessageBox`/legacy tab patterns.
