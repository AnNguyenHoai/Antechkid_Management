# Finance Workspace Audit — 2026-09-23

Original audit base: `main_repos@0ce14e94b0fa5b6ebc45790a13e265586962a887`  
Wave-2 audit base: `main_repos@e12b7f56cb8e3336bfe535f287ad92ee5845a473`  
Wave-2 branch: `codex/finance-audit-wave-2`

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

The original symptom — newly created Income/Expense visible on Dashboard but missing from the list — had two independent root causes: Finance-period permission mismatch and period selection resolving from day 1 while creation used today. Those paths were fixed in the first Finance audit wave.

The second audit pass on `main_repos@e12b7f56...` found an additional cross-surface period-boundary defect: a superseded FinancePeriod configuration could still expose the remainder of its theoretical calendar bucket beyond `effective_to`. Because Expense is date-scoped while Income stores `finance_period_start`, this could make Dashboard, Expense, Outstanding and Settlement disagree around a mid-bucket configuration transition. Wave 2 clips every configuration-backed period to its effective lifetime.

Wave 2 also projects fine-grained `finance.income.*` / `finance.expense.*` capabilities into list-page mutation controls while retaining service authorization as the authoritative boundary.

No evidence was found that DataTable pagination, SQLite persistence, or server-side list loading itself was dropping transactions.

## Correctness findings fixed in the first audit wave

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

**Fix:** runtime Qt and repository/service regressions cover the affected contracts.

### F-07 — Finance used a private EventBus instead of the application bus — MEDIUM/HIGH — FIXED

Finance Workspace previously risked creating a private fallback EventBus instead of participating in the application-wide event stream.

**Fix:** Finance Workspace reuses the explicit/shared CollaborationManager application bus before any compatibility fallback, and aligns Income/Expense mutation events to that bus.

### F-08 — Home Finance card could remain stale after Finance mutations — MEDIUM — FIXED

HomeDashboardService caches workspace summaries and previously did not invalidate that cache on Finance mutations.

**Fix:** HomeDashboardService subscribes to `FinanceDataChanged` and invalidates its cache. The card label was also corrected from misleading `Revenue` to `Tuition paid` because the value comes from Outstanding tuition payments rather than total Income.

### F-09 — Settlement UI authorization was broader than service authorization — MEDIUM — FIXED

FinancialSettlementService permits save/confirm only for Admin, but the UI previously enabled inputs whenever the application entered WRITE mode.

**Fix:** Settlement controls require WRITE mode + DRAFT status + Admin. Service enforcement remains authoritative.

### F-10 — Edit could not clear nullable Income/Expense fields — MEDIUM — FIXED

Forms converted blank text to `None`, while update services use `None` to mean “field omitted / leave unchanged”.

**Fix:** edit mode passes explicit empty strings so service normalization can clear nullable values. Create mode retains the existing optional-value behavior. Wave 2 re-verified this on the exact `e12b7f56...` base and intentionally did not duplicate the fix.

### F-11 — Expense filters disagreed with legacy data and Dashboard normalization — MEDIUM — FIXED

Dashboard normalized legacy payment methods, but ExpenseRepository filtering used exact persisted strings.

**Fix:** repository filters use canonical equivalence groups. Count/list/export share the same filtered query so totals and exported rows remain consistent.

### F-12 — Settlement could undercount legacy Expense payment methods — HIGH — FIXED

Dashboard recognized Vietnamese legacy payment-method labels, but Settlement did not originally bucket all legacy values.

**Fix:** Settlement maps `TÀI KHOẢN CÁ NHÂN` to Cash and `TÀI KHOẢN CÔNG TY` to Bank as well.

## Correctness findings fixed in wave 2

### F-20 — Superseded FinancePeriod leaked past `effective_to` — HIGH — FIXED IN WAVE 2

`FinancePeriodDefinition.period_for_date()` correctly calculates a theoretical calendar bucket, but production read surfaces were using that bucket directly even when the owning configuration had been superseded before the theoretical bucket ended.

Example:

- configuration A: effective `01/01/2026`, duration 3 months;
- configuration B: effective `15/02/2026`;
- configuration A therefore has `effective_to = 14/02/2026`;
- theoretical A bucket for `01/02/2026` is `01/01–31/03`.

Without lifecycle clipping, an old-period view could include Expense/enrollment activity after 14/02 while the new configuration also owns those dates.

**Fix:** `FinancePeriodDefinition.period_for_configuration()` clips the theoretical bucket to the configuration lifetime. Finance Workspace, Dashboard fallback resolution, Outstanding and Settlement now use lifecycle-bounded periods. The original three-argument `FinancePeriodService.get_period_bounds()` retains its mathematical compatibility semantics; production callers pass `effective_to` when a concrete configuration owns the query.

### F-18 — Mutation controls were only WRITE-mode gated — MEDIUM — FIXED IN WAVE 2

Income/Expense services already enforce fine-grained capabilities, but list-page buttons/context actions were enabled from collaboration WRITE state alone.

**Effect:** custom roles could see and invoke an action that the service would reject only after interaction.

**Fix:** Income and Expense mutation controls now require both WRITE state and their matching capability:

- `finance.income.create` / `finance.income.update` / `finance.income.delete`;
- `finance.expense.create` / `finance.expense.update` / `finance.expense.delete`.

Service guards remain authoritative. UI gating only prevents misleading actions and does not grant permissions.

## Remaining findings / product decisions

### F-13 — Historical month/year selector is ambiguous for mid-month FinancePeriods — MEDIUM — FOLLOW-UP

A calendar month can overlap two canonical FinancePeriods, for example `15/08–14/09` and `15/09–14/10`. A plain “September 2026” selector cannot identify which one the user means.

Lifecycle clipping in F-20 prevents cross-configuration leakage, but it does not solve selection ambiguity.

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

This is internally consistent with the current model and regression tests, but it is not equivalent to accounting period closure.

**Decision needed:** if “Confirm Settlement” is intended to close a period, add a domain-level closed-period guard to Income/Expense create/update/void/delete. If it is only a reconciliation snapshot, rename/explain the behavior clearly.

### F-17 — Class fee semantics for multi-month FinancePeriods are not explicit — MEDIUM — PRODUCT RULE REQUIRED

Outstanding applies `Class.fee` once per FinancePeriod regardless of `duration_months`. The model does not state whether `fee` is monthly, per course, or per FinancePeriod.

**Decision needed before changing calculation:** define the billing meaning of `Class.fee`. Do not multiply automatically without this rule.

### F-21 — Backdated FinancePeriod reconfiguration can reclassify Expense but not existing Income — HIGH — PRODUCT RULE REQUIRED

FinancePeriod administration allows a new configuration with an effective date in the past and allows a configuration to be truncated. Income persists the `finance_period_start` that was canonical when the Income was created; Expense does not persist period membership and is derived from payment date at read time.

**Risk:** after a retroactive configuration change, Expense automatically follows the new date boundary while existing Income can retain its old `finance_period_start`. A transaction may then disappear from the newly resolved Income period even though Expense for the same dates moves to the new period.

This is not safe to repair implicitly because confirmed settlements and audit history may already reference the old classification.

**Decision needed:** choose one explicit policy:

1. prohibit retroactive FinancePeriod changes once affected financial activity/settlements exist; or
2. provide an audited reclassification/migration operation that updates affected Income and defines how confirmed Settlement snapshots are handled.

### F-19 — Finance UI still has legacy production-UX debt — LOW/MEDIUM — FOLLOW-UP

Finance surfaces still contain `QMessageBox`, emoji/raw literals, mixed Vietnamese/English copy, older forms/detail dialogs, and an unused `finance_list_page.py` placeholder.

**Recommendation:** handle this in the dedicated Finance UI-PROD migration rather than mixing broad visual churn into correctness fixes.

### Composition cleanup — LOW — FOLLOW-UP

Production Finance can recover the application EventBus from CollaborationManager, so mutation refresh is functionally correct. MainWindow still does not explicitly pass `event_bus` / `notification_service` into `FinanceWorkspaceShell`, and app composition constructs Income/Expense without an explicit event bus before the shell aligns them.

**Recommendation:** make those dependencies explicit in the composition root during the Finance UI-PROD migration; do not mix the broad constructor churn into this correctness patch.

## Verified healthy boundaries

- Income and Expense lists use real server pagination.
- DataTable server mode is not the missing-transaction root cause.
- Income update recalculates canonical `finance_period_start` when payment date changes.
- Outstanding is read-only and derives from Enrollment + ACTIVE Tuition Income.
- VOIDED / soft-deleted Income is excluded from live money calculations.
- Expense Pending is excluded from realized Dashboard/Settlement outflow; legacy `Paid` remains realized.
- Settlement recalculates live activity before confirmation and freezes a confirmed snapshot.
- Finance service authorization remains authoritative even when UI projects permissions.
- WriteTransactionManager publishes the database on Finish Editing regardless of its convenience `_has_changes` flag; Finance is not silently omitted from publish for lack of a `mark_dirty()` event handler.

## Wave-2 regression gates

Runtime coverage added in wave 2 includes:

1. lifecycle clipping of a theoretical FinancePeriod bucket at `effective_to`;
2. preservation of the legacy three-argument mathematical period helper;
3. Finance Workspace shared-period lifecycle bounds;
4. Dashboard fallback lifecycle bounds;
5. Outstanding lifecycle bounds;
6. Settlement lifecycle bounds;
7. Income create/update/delete capability projection combined with WRITE state;
8. Expense create/update/delete capability projection combined with WRITE state;
9. denied UI capability stops before requesting a collaboration write lock.

## Release recommendation

Wave 2 is a narrow Finance correctness patch: merge only after the focused Finance regressions and the full Windows pytest suite pass. F-13, F-14, F-15, F-16, F-17 and F-21 require explicit product/accounting decisions before code changes. F-19 and composition cleanup belong in the dedicated Finance UI-PROD migration.
