# Finance Workspace Audit — Pass 3 — 2026-09-23

Base: `main_repos@e888b29a6f111c5170dd487699b4773c2ac13075`  
Branch: `codex/finance-audit-pass-3`

## Scope

This pass continues beyond the UI visibility fixes from PR #326 and focuses on financial-integrity boundaries that can make a persisted transaction appear in the wrong period, make a successful commit look like a failed save, or rewrite historical read models.

Reviewed areas:

- FinancePeriod transition semantics;
- Income / Expense mutation transaction boundaries;
- legacy Expense compatibility in form/detail/dashboard;
- Dashboard and Settlement aggregation completeness;
- Outstanding historical correctness;
- enrollment validation at transaction date;
- audit/lifecycle boundaries that remain intentionally undecided.

## Executive result

PR #326 fixed the originally reported missing-transaction issue and passed its regression gate. Pass 3 found additional defects that were not covered by that audit.

Two legacy Expense UI defects are fixed in this branch because they are unambiguous and do not change accounting rules. The remaining HIGH findings are domain/service problems and should be addressed in dedicated follow-up patches with regression tests before the Finance workspace is considered fully production-hardened.

## Findings

### F-20 — FinancePeriod transition can create overlapping effective buckets — HIGH — OPEN

`FinancePeriodService.configure()` truncates the previous configuration by setting `effective_to = new_effective_from - 1 day`. However, most Finance readers calculate the bucket from `effective_from + duration_months` and do not clamp the calculated bucket end to the configuration's `effective_to`.

Example:

- old configuration: effective from `15/08/2026`, duration 1 month;
- new configuration: effective from `01/09/2026`.

The old configuration can still calculate `15/08–14/09`, while the new configuration calculates `01/09–30/09`. Those ranges overlap for 14 days.

**Impact:**

- Expense, Settlement and Outstanding are primarily date-based and can include the same date range under two different configuration contexts;
- Income stores `finance_period_start` at mutation time, so it can disagree with date-based Expense after a configuration transition;
- a confirmed Settlement can become difficult to reach from the newly resolved period context.

**Required fix direction:** introduce one canonical effective-period resolver that clamps natural bucket bounds to the owning configuration's effective range and make Dashboard, Expense, Outstanding and Settlement use it.

### F-21 — Retroactive FinancePeriod configuration can stale existing Income classification — HIGH — OPEN / POLICY REQUIRED

Income persists `finance_period_start` when a row is created or edited. Adding a new FinancePeriod configuration in the past changes which configuration now covers existing payment dates, but existing Income rows are not reclassified.

**Impact:** an Income row can retain an old `finance_period_start` even though current period resolution says its `payment_date` belongs to a different period. Period-scoped Income/Dashboard/Outstanding queries can then omit the row.

A later edit recalculates `finance_period_start`, so edited and untouched rows with equivalent historical dates can end up classified differently.

**Decision required:**

1. prohibit retroactive FinancePeriod changes once affected financial activity exists; or
2. perform an explicit, audited reclassification migration of affected Income and settlement state.

Silent retroactive reclassification must not be introduced implicitly.

### F-22 — Primary financial commit can be reported as failed when timeline logging fails — HIGH — OPEN

Income and Expense mutations commit the primary transaction first, then write timeline events through a second service/session. Timeline logging can raise.

**Impact:**

- money is already persisted;
- the mutation method raises before returning success;
- `FinanceDataChanged` may never publish;
- the dialog can show an error and the user can retry, creating a duplicate transaction.

This affects create most severely, but update/void/delete can also be reported as failed after state already changed.

**Required fix direction:** committed primary financial state must determine mutation success. Timeline/event projection after commit must be best-effort or be made part of the same atomic transaction. Regression tests should inject a failing timeline writer and verify that a committed transaction returns success exactly once and still refreshes Finance projections.

### F-23 — Legacy Expense `description = NULL` breaks edit/detail/dashboard paths — MEDIUM/HIGH — FIXED IN THIS BRANCH

`Expense.description` is nullable in the persisted model, while the current creation service requires a description. Legacy rows can therefore contain NULL.

Before this branch:

- Expense Form called `setPlainText(None)`;
- Expense Detail called `setText(None)`;
- Finance Dashboard sliced and measured `None` directly.

A single legacy row could reject edit/detail or force the whole Finance Dashboard into its Error state.

**Fix:** all three surfaces now render NULL safely. Edit preserves an untouched legacy NULL instead of forcing an unrelated edit to repair historical data.

### F-24 — Unknown legacy Expense category can be silently rewritten on edit — HIGH — FIXED IN THIS BRANCH

Current Expense categories are a closed canonical list, but historical/test data includes older values such as `Rent` and `Material`.

Previously `findText()` failed for an unknown category and the combo remained on its first item (`Teacher Salary`). Saving an unrelated field could rewrite the legacy category or be rejected by current validation.

**Fix:** the form adds and selects the persisted legacy category for display. If it remains unchanged, category is omitted from the update payload. Selecting a current canonical category still performs a normal validated update.

### F-25 — Dashboard and Settlement contain silent aggregation caps — MEDIUM — OPEN

Finance Dashboard commonly requests at most 10,000 rows for totals; Financial Settlement reads at most 100,000 rows per period.

**Impact:** at high volume, totals can be silently understated instead of failing visibly.

**Required fix direction:** use count-driven paging or database aggregation. Financial totals must never depend on an arbitrary UI/service row cap.

### F-26 — Historical Outstanding uses the current `Class.fee` value — HIGH — OPEN / MODEL RULE REQUIRED

Outstanding derives historical expected tuition from `class_obj.fee` at read time. `ClassService.update_class()` allows the fee to change.

**Impact:** changing a class fee today can rewrite the expected tuition and outstanding amount shown for old FinancePeriods, even though historical payments did not change.

This is separate from the existing question of whether `Class.fee` is monthly, per course, or per FinancePeriod.

**Decision required:** define a historical fee source of truth, for example an enrollment fee snapshot or effective-dated tuition policy. Historical Finance reports must not depend on a mutable current class field unless that is explicitly the business rule.

### F-27 — Income enrollment validation checks current ACTIVE status, not payment date — HIGH — OPEN

`IncomeService.create_income()` validates student/class ownership through `EnrollmentRepository.exists(..., active_only=True)`. That checks the enrollment's current `status == ACTIVE`, not whether the enrollment covered `payment_date`.

**Impact:**

- a legitimate backdated payment can be rejected after the enrollment has been COMPLETED/WITHDRAWN;
- a currently ACTIVE enrollment can accept a payment dated before its `start_date`.

Outstanding already uses enrollment `start_date/end_date`, so Finance currently has two inconsistent definitions of enrollment validity.

**Required fix direction:** add a date-aware enrollment lookup and validate student-linked Income against the transaction date. Historical/archived entity policy should be tested explicitly.

### F-28 — Historical Income edit can display the wrong student/class when referenced entities are no longer in active pick lists — MEDIUM — OPEN

Income edit loads active students/classes into combo boxes, then tries to select the persisted IDs. If the historical student/class is archived and absent from those lists, the combo can remain on an unrelated first item. Identity fields are disabled, so this does not rewrite the Income, but it displays false transaction identity to the operator.

**Required fix direction:** inject the persisted referenced entity into the disabled edit selector when it is not present in the active list, or replace edit-mode selectors with immutable detail fields.

### F-29 — `Other` Income source description is conflated with mutable note text — MEDIUM — OPEN / MODEL DEBT

For unlinked `Other` Income, the form stores the source description inside `Income.note`. Edit mode shows that same note as both the locked source description and editable note text. Editing the note can therefore overwrite what the UI presents as immutable source identity.

**Required fix direction:** separate source description from free-form note in the data contract, or stop presenting the description as immutable identity until it has its own persisted field.

### F-30 — Income service still permits soft-delete of an ACTIVE transaction — MEDIUM — OPEN / LIFECYCLE DEBT

The UI only exposes Delete for VOIDED Income, but `IncomeService.delete_income()` intentionally remains backward-compatible with callers that soft-delete ACTIVE rows.

**Risk:** a caller with delete capability can remove live money without the explicit void-reason lifecycle that the UI enforces.

**Recommended direction:** inventory all non-UI callers. If none require the legacy path, make VOIDED a service-level precondition for soft delete and keep the void audit trail authoritative.

## Verified healthy items in Pass 3

- PR #326 is merged at `e888b29a6f111c5170dd487699b4773c2ac13075`.
- Existing Expense list rendering already handles nullable description safely.
- Expense CSV export writes nullable description/note safely.
- EventBus handler exceptions are caught and logged; the post-commit false-failure problem is specifically the separate timeline write before event publication.
- FinancePeriod repository effective-date lookup itself respects `effective_from/effective_to`; the overlap defect occurs when callers expand a natural bucket beyond the configuration's effective end.
- Income export is count-driven and does not use the Dashboard 10,000-row cap.
- Outstanding loads all Tuition Income using count-driven reads; its main historical risk is mutable fee semantics, not payment pagination.

## Regression coverage added in this branch

1. legacy Expense category is preserved during unrelated edits;
2. legacy NULL Expense description loads in the edit form;
3. legacy NULL Expense description renders in detail view;
4. Finance Dashboard accepts a recent Expense with NULL description without entering Error state.

## Recommended next sequence

1. F-20 canonical effective-period bounds and transition tests.
2. F-22 post-commit mutation success / best-effort timeline projection.
3. F-27 date-aware enrollment validation for Income.
4. F-25 remove aggregation caps.
5. Decide F-21 retroactive period policy and F-26 historical tuition-fee source before changing data semantics.
6. Then continue F-13/F-15/F-16/F-17/F-18/F-19 from the previous audit and the dedicated Finance UI-PROD migration.
