# FIN-FIX-01 — Income void/delete, course balances and Student Finance projection

## Audited source of truth

1. IncomeService mutates the ledger (ACTIVE → VOIDED → soft-deleted) and emits `FinanceDataChanged` **after commit**.
2. IncomeRepository.sum_active_tuition_for_enrollment is the shared settlement aggregation used by OutstandingService. It excludes VOIDED and soft-deleted Income, and adds immutable non-cash tuition CREDIT_ADJUSTMENT plus transfers.
3. Finance Workspace already subscribes to the finance event; Student Workspace previously did **not**. Student Profile could show stale summary/history despite an updated ledger.
4. The `total_paid` domain value represents **settled tuition** (cash + non-cash credit + transfers), **not solely actual cash receipts**. Student Profile now labels it as tuition settled, without changing the canonical calculation or mixing finance periods.

## Implemented

- Student Workspace subscribes to the shared committed finance event and refreshes the currently selected student's finance tab, rather than computing balances separately or refreshing every student page.
- Payment-time CREDIT_ADJUSTMENT created together with Income now stores a deterministic audit-safe receipt identity `tuition-payment-credit:income:<id>` in the existing adjustment idempotency key; creation remains one DB transaction.
- EDIT, VOID and soft DELETE of the same Income are rejected when it has a coupled immutable payment-time credit; an old UUID-only payment-time credit in the same Enrollment also blocks ambiguous mutations. **No automatic deletion, revision or reversal of immutable adjustments** is attempted.
- Ordinary Tuition Income **without** payment-time credits is still voided/deleted by existing service logic. After commit, the shared ledger query excludes the affected amount, and both Finance and Student views refresh from their read services.
- Add regression tests for canonical balance before/after VOID and soft deletion, ambiguous/coupled credits, unrelated payments, Student refresh event and source contract.

## Known limitation / follow-up financial design

Prior payment-time credits have `tuition-payment-credit:<uuid>` keys with **no verifiable Income foreign key**. It is not safe to infer which payment created them. A later dedicated adjustment-reversal design may provide an auditable **compensating** credit entry and explicit linked-income identity. Until then, the affected Enrollment's ambiguous payment edits must be stopped with an actionable validation message.

**Do not** simply remove a credit, silently leave it after voiding its coupled cash transaction, or treat a cash receipt as equivalent to tuition settled. A historical correction requires a deliberate finance reconciliation workflow.

## Acceptance gates

- [ ] Full Windows CI shards passed on exact PR commit.
- [ ] UI test: VOID normal Tuition Income in Finance and verify Student Profile summary, table and payment history refresh immediately without navigating away.
- [ ] UI test: soft-delete VOIDED Income then inspect both Finance and Student. Confirm finance period and class/enrollment identities are unchanged.
- [ ] UI test: payment-time discount coupled to Income is blocked on edit/void/delete; data and totals remain unchanged.
- [ ] UI test: legacy ambiguous discounts are surfaced for manual reconciliation; no automatic reversal.
- [ ] Verify direct TuitionAdjustment events refresh both workspaces and READ-only finance permissions remain enforced.
- [ ] Windows EXE UAT and founder acceptance; do not merge if data integrity assertions fail.

This PR is narrowly scoped to FIN-FIX-01; it does not introduce offline READ, Cancel Editing or zero-amount Income.
