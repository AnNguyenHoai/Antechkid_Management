# SETTLEMENT-FIX-01 — Save Draft Recovery Outbox and live Expected Closing

## Root causes

1. For a newly created FinancialSettlement DRAFT, SQLAlchemy has not assigned `row.id` until flush. The Recovery Outbox receives `summary_args={"settlement_id": None}` and rejects it as a non-scalar. Since the error occurs before commit, the draft does not persist. Existing CONFIRM used a flush already, causing different behavior.
2. Expected Closing/Difference were only recalculated when the page refreshed from `get_preview`. Typing Opening/Actual values did not recalculate displayed labels, making the valid unsaved inputs look ignored.

## Changes

- Flush FinancialSettlement once inside `FinancialSettlementService._save()`, both Draft and Confirm, before audit/Recovery Outbox. Do not loosen Recovery Outbox type validation; commit remains one atomic transaction.
- When any of Opening Cash, Opening Bank, Actual Cash, Actual Bank changes, recalculate an **unsaved local projection** using the same `FinancialSettlementService._calculate` formula and the last successfully loaded canonical wallet totals.
- Never save or publish from a text-input event. The `Save Draft` button persists the opening/actual inputs, and `Confirm` re-aggregates authoritative totals in its service transaction.
- The page suppresses transient preview recalculation while refreshing values and does not project when the period is unavailable.
- Regression covers first draft identity, outbox rejection before commit, live expected/difference, and nullable Actual values.

## Windows UAT

1. With valid WRITE, open a period without a Settlement. Input Opening Cash and Bank, verify Expected Closing changes immediately and equals Opening + System Income - System Expense.
2. Enter Actual Cash/Bank. Verify Difference = Actual - Expected. Clearing Actual leaves Difference blank/dash rather than a false zero.
3. Save Draft. Verify there is no Recovery summary exception and the values persist after leaving the page and opening again.
4. Modify Opening, Save Draft again, verify values are updated (no duplicate settlement), then Confirm as admin. Check outbox/audit and period closure.
5. Confirm with a difference but without reason must fail before commit. Reopen retains existing audited flow.
6. Simulate an outbox or permission error. No settlement should be committed; entries in the UI must remain editable for retry.
7. With READ mode, input controls and Save/Confirm are disabled.

No database schema changes, Git authority changes, or relaxation of Recovery validation. Keep PR Draft until CI and Windows EXE UAT.
