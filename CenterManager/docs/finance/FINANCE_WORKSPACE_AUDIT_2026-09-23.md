# Finance Workspace Audit — 2026-09-23

Base: `main_repos@0ce14e94b0fa5b6ebc45790a13e265586962a887`  
Fix branch / PR: `codex/finance-workspace-audit-fixes` / #326

## Scope

Audit covers the Finance workspace end to end:

- shared FinancePeriod context and navigation;
- Dashboard;
- Income CRUD/list/filter/export;
- Expense CRUD/list/filter/export;
- Outstanding read model;
- Financial Settlement;
- FinancePeriod administration;
- application event refresh and Home projection consistency;
- write mode and authorization boundaries;
- legacy-data compatibility;
- regression-test quality.

## Executive result

The original symptom — newly created Income/Expense visible on Dashboard but missing from the list — had two independent root causes: Finance-period permission mismatch and period selection resolving from day 1 while creation used today. Both are fixed in PR #326.

The second audit pass found additional consistency defects that did not necessarily lose persistence but could produce stale projections, silently preserve values a user tried to clear, or make Dashboard/list/Settlement disagree on legacy Expense data. Those defects are also fixed in the same PR and covered by runtime regression tests.

No evidence was found that DataTable pagination, SQLite persistence, or server-side list loading itself was dropping transactions.

## Correctness findings fixed in PR #326

### F-01 — Finance role could not resolve the active period — HIGH — FIXED

Finance Workspace is entered with `finance.view`, but `FinancePeriodService.get_active_period()` previously required `finance.period.view`. The default Finance role owns `finance.view` but not `finance.period.view`.

**Effect:** Finance users could enter the workspace while Income/Expense/Outstanding resolved no period. Dashboard global “Today” values could still show money, creating the exact reported symptom.

**Fix:** active-period resolution now belongs to the `finance.view` read contract. Period history/configuration management remains separately protected.

### F-02 — Current-month selector resolved from day 1 — HIGH — FIXED

A FinancePeriod may begin mid-month. The old month/year selector always used day 1, while create forms used today.

**Effect:** the visible list and the newly created transaction could resolve different FinancePeriods.

**Fix:** the current selected month resolves from today. Historical/future month selection retains day-1 compatibility pending a canonical period-selector redesign.

### F-03 — Create form date was not bound to the visible period — HIGH — FIXED

Income/Expense forms always defaulted to today even when the user was viewing another FinancePeriod.

**Fix:** create dialogs receive an initial date guaranteed to belong to the visible period. Today remains preferred when it belongs to that period.

### F-04 — Newly created row could remain off-screen on another page — MEDIUM — FIXED

A create while viewing page 2+ refreshed the same server page although newest-first data belongs on page 1.

**Fix:** successful create resets Income/Expense to page 1 before refresh.

### F-05 — Expense edit could silently change payment method/status — HIGH — FIXED

Persisted canonical values (`Cash`/`Bank`, `Completed`/`Pending`) did not match localized combo labels. `findText()` could fail and leave the first option selected.

**Effect:** editing an unrelated field could rewrite a `Bank` / `Pending` transaction as `Cash` / `Completed`.

**Fix:** combo labels carry canonical item data, edit uses `findData()`, and save uses `currentData()`. Legacy `Bank Transfer`, Vietnamese account labels and `Paid` are normalized on load.

### F-06 — Source-only tests allowed false positives — MEDIUM — FIXED FOR AFFECTED PATHS

Earlier tests searched source text for tokens such as `Cash`, `Bank`, `Completed`, `Pending` and `currentData()`. Comments could satisfy these assertions even when runtime behavior was broken.

**Fix:** PR #326 adds runtime Qt and repository/service regressions for the affected contracts.

### F-07 — Finance used a private EventBus instead of the application bus — MEDIUM/HIGH — FIXED

Production creates one application EventBus and injects it into CollaborationManager, but Finance Workspace previously created its own fallback EventBus because MainWindow did not pass one explicitly. Income/Expense mutations therefore refreshed Finance internally but did not participate in the application-wide event stream.

**Fix:** Finance Workspace now reuses, in order, an explicitly supplied bus, the CollaborationManager application bus, an already-bound Finance service bus, and only then a local compatibility fallback. Income and Expense are aligned onto that shared bus.

### F-08 — Home Finance card could remain stale after Finance mutations — MEDIUM — FIXED

HomeDashboardService caches workspace summaries and previously invalidated only on selected Student events. Returning Home calls a normal refresh, which reuses the cache.

**Effect:** after a payment/expense change, Finance could be current while the Home Finance card still showed old values.

**Fix:** HomeDashboardService subscribes to `FinanceDataChanged` and invalidates its cache. The card label was also corrected from misleading `Revenue` to `Tuition paid`, because the value comes from Outstanding tuition payments rather than total Income.

### F-09 — Settlement UI authorization was broader than service authorization — MEDIUM — FIXED

FinancialSettlementService permits save/confirm only for Admin, but the UI previously enabled inputs whenever the application entered WRITE mode.

**Fix:** Settlement controls now require WRITE mode + DRAFT status + Admin. Service enforcement remains authoritative.

### F-10 — Edit could not clear nullable Income/Expense fields — MEDIUM — FIXED

Forms converted blank text to `None`, while update services use `None` to mean “field omitted / leave unchanged”.

**Effect:** users could erase a note/payment-period/paid-by field in the form, save successfully, and still see the old value afterward.

**Fix:** edit mode passes explicit empty strings so service normalization can clear nullable values. Create mode retains the existing optional-value behavior.

### F-11 — Expense filters disagreed with legacy data and Dashboard normalization — MEDIUM — FIXED

Dashboard normalized legacy payment methods, but ExpenseRepository filtering used exact persisted strings.

**Effect:** filtering `Bank` could omit `Bank Transfer` / `TÀI KHOẢN CÔNG TY`; filtering `Cash` could omit `TÀI KHOẢN CÁ NHÂN`; filtering `Completed` could omit legacy `Paid` rows.

**Fix:** repository filters now use canonical equivalence groups. Count/list/export share the same `_filtered_query`, so totals and exported rows remain consistent.

### F-12 — Settlement could undercount legacy Expense payment methods — HIGH — FIXED

Dashboard recognized Vietnamese legacy payment-method labels, but Settlement only bucketed `Cash`, `Bank`, and `Bank Transfer`.

**Effect:** a legacy realized Expense could reduce Dashboard cash/bank totals but be absent from Settlement reconciliation.

**Fix:** Settlement now maps `TÀI KHOẢN CÁ NHÂN` to Cash and `TÀI KHOẢN CÔNG TY` to Bank as well.

## Remaining findings / product decisions

### F-13 — Historical month/year selector is ambiguous for mid-month FinancePeriods — MEDIUM — FOLLOW-UP

A calendar month can overlap two canonical FinancePeriods, for example `15/08–14/09` and `15/09–14/10`. A plain “September 2026” selector cannot identify which one the user means.

**Recommended product direction:** replace month/year inference with a canonical selector showing exact period bounds, e.g. `15/09/2026 – 14/10/2026`, with “Current period” as the default.

### F-14 — Expense can exist without a FinancePeriod configuration — MEDIUM — PRODUCT RULE REQUIRED

Income creation requires a covering FinancePeriod and stores its canonical start. Expense creation remains date-based and does not require a covering FinancePeriod.

This can legitimately produce an Expense that exists in persistence and may affect global “Today”, while period-scoped views have no period to display it in.

**Decision needed:** either require a covering FinancePeriod for Expense mutation, or explicitly support an “unassigned/unscoped expense” state and expose it in the UI.

### F-15 — Future-dated transaction semantics differ across Finance surfaces — MEDIUM/HIGH — PRODUCT RULE REQUIRED

Current-period Dashboard revenue/expense is clamped to today. Income/Expense lists default to the full selected period. Outstanding and Settlement aggregate the full period end. Services currently allow future payment dates.

**Effect:** if future-dated postings are intentionally entered, Dashboard current-period totals can differ from list / Outstanding / Settlement without any database defect.

**Decision needed:** either prohibit future-dated realized postings, or define separate “posted to date” vs “full-period scheduled” semantics consistently across every Finance surface.

### F-16 — Confirmed Settlement freezes the snapshot, not the underlying ledger — MEDIUM/HIGH — PRODUCT RULE REQUIRED

Confirmed settlements are immutable snapshots, but Income/Expense mutations in that same period are not locked afterward.

This is internally consistent with the current model name and implementation, but it is not equivalent to accounting period closure.

**Decision needed:** if “Confirm Settlement” is intended to close a period, add a domain-level closed-period guard to Income/Expense create/update/void/delete. If it is only a reconciliation snapshot, rename/explain the behavior clearly.

### F-17 — Class fee semantics for multi-month FinancePeriods are not explicit — MEDIUM — PRODUCT RULE REQUIRED

Outstanding applies `Class.fee` once per FinancePeriod regardless of `duration_months`. The model does not state whether `fee` is monthly, per course, or per FinancePeriod.

**Decision needed before changing calculation:** define the billing meaning of `Class.fee`. Do not multiply automatically without this rule.

### F-18 — Mutation controls are still mostly WRITE-mode gated — LOW/MEDIUM — FOLLOW-UP

Income/Expense service methods enforce fine-grained capabilities, but list-page buttons/context actions are primarily enabled by collaboration WRITE state. A custom role can therefore see an action that the service will reject.

**Recommendation:** project `finance.income.*` / `finance.expense.*` capabilities into each UI action while retaining service checks.

### F-19 — Finance UI still has legacy production-UX debt — LOW/MEDIUM — FOLLOW-UP

Finance surfaces still contain `QMessageBox`, emoji/raw literals, mixed Vietnamese/English copy, older forms/detail dialogs, and an unused `finance_list_page.py` placeholder.

**Recommendation:** handle this in the dedicated Finance UI-PROD migration rather than mixing broad visual churn into correctness fixes.

## Verified healthy boundaries

- Income and Expense lists use real server pagination.
- DataTable server mode is not the missing-transaction root cause.
- Income update recalculates canonical `finance_period_start` when payment date changes.
- Outstanding is read-only and derives from Enrollment + ACTIVE Tuition Income.
- VOIDED / soft-deleted Income is excluded from live money calculations.
- Expense Pending is excluded from realized Dashboard/Settlement outflow; legacy `Paid` remains realized.
- Settlement recalculates live activity before confirmation and freezes a confirmed snapshot.
- Finance service authorization remains authoritative even when UI projects permissions.
- WriteTransactionManager publishes the database on Finish Editing regardless of its convenience `_has_changes` flag; Finance was not at risk of being silently omitted from publish for lack of a `mark_dirty()` event handler.

## Regression gates in PR #326

Runtime coverage now includes:

1. Finance viewer active-period resolution via `finance.view`.
2. Current-month mid-month FinancePeriod resolution.
3. Historical selection compatibility behavior.
4. Income/Expense create-date binding to visible period.
5. Expense canonical and legacy edit restoration.
6. Explicit clearing of nullable Income/Expense edit fields.
7. Legacy Expense payment/status filter equivalence.
8. Settlement legacy Cash/Bank bucketing.
9. Settlement Admin-only edit projection.
10. Finance Workspace reuse of the application EventBus.
11. Home cache invalidation on `FinanceDataChanged`.

## Release recommendation

PR #326 should be treated as the Finance correctness/consistency gate. After its final CI is green, the next Finance task should focus on F-13 through F-19, with product decisions made first for future-dated postings, period closure and fee semantics. A dedicated Finance UI-PROD migration can then modernize the visual layer without changing accounting rules implicitly.
