# Finance Workspace Audit — 2026-09-23

Base: `main_repos@0ce14e94b0fa5b6ebc45790a13e265586962a887`

## Scope

Audit covers the Finance workspace end to end:

- shared FinancePeriod context and navigation;
- Dashboard;
- Income CRUD/list/filter/export;
- Expense CRUD/list/filter/export;
- Outstanding read model;
- Financial Settlement;
- FinancePeriod administration;
- event refresh, write mode and authorization boundaries;
- regression-test quality.

## Executive result

The reported symptom — a newly created Income/Expense appearing on Dashboard but not in the transaction list — is reproducible from the source through two independent period-resolution defects. Both are correctness issues and are fixed by PR #326.

The broader Finance data/service boundaries are mostly sound: Income owns a canonical `finance_period_start`, Expense is period-scoped by payment date, Dashboard/Settlement use service-owned aggregation, Outstanding remains derived/read-only, and write mutations remain service-authorized. The remaining findings are primarily authorization UX, integration wiring and production UI debt.

## Correctness findings

### F-01 — Finance role cannot resolve the active period — HIGH — FIXED

**Before:** Finance Workspace access is granted by `finance.view`, while `FinancePeriodService.get_active_period()` required `finance.period.view`. The default Finance role owns `finance.view` and Finance CRUD capabilities but not `finance.period.view`.

**Effect:** a Finance user can enter the workspace, but shared period resolution fails. Income/Expense/Outstanding become empty period-scoped views while Dashboard can still show global “Today” values.

**Fix:** active-period resolution now uses the `finance.view` read contract. Administrative configuration listing remains guarded by `finance.period.view`, and management remains Admin-only.

### F-02 — Current-month selector resolved from day 1 — HIGH — FIXED

**Before:** selecting a month/year always produced `<year>-<month>-01`. FinancePeriod configurations may begin on any effective date. A period starting mid-month can therefore resolve a different bucket — or no configuration at all — than today.

**Effect:** the workspace can display one FinancePeriod while the create dialog defaults to today and saves the transaction into another period. Dashboard “Today” sees the transaction; the selected list does not.

**Fix:** the currently selected current month resolves from `date.today()`. Historical/future month selection keeps the previous day-1 behavior for compatibility; see F-08 for the remaining UX ambiguity.

### F-03 — New transaction date not bound to visible period — HIGH — FIXED

**Before:** Income and Expense create forms always defaulted to the machine’s current date, regardless of the FinancePeriod currently displayed.

**Fix:** list pages pass an `initial_payment_date` guaranteed to belong to the currently visible period. If today is inside the period it remains the preferred default.

### F-04 — Newly created row can remain off-screen on another page — MEDIUM — FIXED

**Before:** after create, server-paged lists refreshed the current page. If the user was on page 2+, the newly created newest-first record could exist on page 1 and appear “missing”.

**Fix:** successful create resets the list to page 1 before refresh.

### F-05 — Editing Expense can silently change payment method/status — HIGH — FIXED

**Before:** Expense persisted canonical values (`Cash`/`Bank`, `Completed`/`Pending`) while edit combos displayed Vietnamese labels and restored selection with `findText()`. `Bank` and `Pending` could therefore fail to restore and remain on the first option. Saving an unrelated edit could silently rewrite the transaction as `Cash` + `Completed`.

**Fix:** combo display labels now carry canonical values as item data; load uses `findData()` and save uses `currentData()`.

### F-06 — Source-only tests allowed false positives — MEDIUM — FIXED FOR AFFECTED PATH

The previous Expense form regression test only searched source text for strings such as `"Cash"`, `"Bank"` and `currentData()`. Those tokens were present in comments, so CI could pass while runtime behavior was wrong.

PR #326 adds runtime Qt tests for canonical Expense edit restoration, create-date context and period permission behavior.

## Follow-up findings

### F-07 — Shared event bus and notification service are not explicitly wired — MEDIUM — FOLLOW-UP

`MainWindow` constructs Finance Workspace without explicitly passing the application `event_bus` or `notification_service`. Finance Workspace repairs a missing event bus internally and therefore intra-Finance refresh currently works, but this is weaker than the single-composition-root contract used elsewhere. Notification fallbacks can also become log-only instead of user-visible feedback.

**Recommendation:** make `MainWindow` explicitly inject both dependencies and strengthen the existing Finance event test so it inspects the Finance constructor call rather than accepting the same keyword elsewhere in the file.

### F-08 — Month/year selector is ambiguous for mid-month historical periods — MEDIUM — FOLLOW-UP

A month label is not a unique FinancePeriod when periods can start mid-month. Example: September can intersect both `15/08–14/09` and `15/09–14/10`.

**Recommendation:** replace month/year inference with a canonical period selector such as `15/09/2026 – 14/10/2026`, backed directly by FinancePeriod resolution/history. Keep a “current period” default.

### F-09 — Settlement UI authorization is broader than service authorization — MEDIUM — FOLLOW-UP

`FinancialSettlementService` permits save/confirm only for Admin, while the page enables editing based on collaboration WRITE state. A non-Admin Finance user can therefore see enabled controls that are guaranteed to fail at the service boundary.

**Recommendation:** project the Admin/capability boundary into the page state while retaining service enforcement as authoritative.

### F-10 — Income/Expense mutation controls are primarily WRITE-mode gated — LOW/MEDIUM — FOLLOW-UP

Service methods correctly enforce fine-grained Finance capabilities, but list UI actions are mostly enabled/disabled from collaboration WRITE state alone. A read-only capability profile may see controls that later fail in the service.

**Recommendation:** enable each mutation action only when both WRITE mode and the corresponding capability are present.

### F-11 — Expense can exist without a FinancePeriod configuration — MEDIUM — FOLLOW-UP

Income creation resolves and stores a canonical FinancePeriod; Expense creation is date-based and does not require a covering FinancePeriod. When no period is configured, an Expense can still exist and Dashboard “Today” can observe it, while period-scoped workspace pages intentionally show no rows.

**Recommendation:** decide the domain contract explicitly. Either require a covering FinancePeriod for Expense mutation, or provide an explicit unscoped/unassigned Expense state instead of silently hiding it from period-scoped views.

### F-12 — Dashboard “Today” and selected-period data use different scopes — LOW — BY DESIGN, NEEDS UX CLARITY

Dashboard intentionally exposes both selected-period KPIs and global today KPIs. This is useful, but when the selected period is unavailable it can look like data inconsistency.

**Recommendation:** visually group “Today” as a separate global snapshot and show an explicit period-error state instead of presenting empty selected-period data as an ordinary zero state.

### F-13 — Finance UI is not yet production-migrated — LOW/MEDIUM — FOLLOW-UP

Finance still contains legacy `QMessageBox`, emoji/raw visual literals, mixed Vietnamese/English copy, and older form/detail patterns. `finance_list_page.py` is an unused “Coming soon” placeholder.

**Recommendation:** handle this as the dedicated Finance UI-PROD migration after correctness fixes are merged; do not mix broad visual churn into the transaction-visibility hotfix.

## Verified healthy boundaries

- Income list uses real server pagination and server-side filtering/sorting.
- Expense list uses server pagination and period-constrained dates.
- DataTable server mode is not the cause of the missing-row report.
- Income update recalculates canonical `finance_period_start` if payment date changes.
- Outstanding is read-only and derives from Finance services rather than owning money mutations.
- Settlement recalculates live totals before confirmation and freezes confirmed snapshots.
- Confirmed settlements are immutable at the service boundary.
- Dashboard aggregation and list queries intentionally have separate read models; the defect was period/context alignment rather than failed database persistence.

## Regression gate added by PR #326

The Finance regression suite now covers:

1. Finance viewer can resolve the active period with `finance.view`.
2. Current-month selection resolves from today for a mid-month FinancePeriod.
3. Historical month selection retains compatibility behavior.
4. Income create form accepts the selected-period date.
5. Expense create form accepts the selected-period date.
6. Expense edit restores canonical `Bank` and `Pending` values at runtime.

## Recommended next task

After PR #326 is green and merged, create a dedicated **Finance Workspace Production Migration** task. Address F-07 through F-13 together with UI-PROD component adoption and a focused physical UAT covering Admin, Finance-role and read-only capability profiles.
