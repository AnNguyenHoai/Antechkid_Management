# Tuition Engine V1 — Group A F-01..F-04 acceptance

**PR #621; not a full Tuition V1 production release.** Class monthly-plan UI remains gated off.
The original Enrollment and Income historical rows are not rewritten.

## F-01: one effective tuition policy
- `calculate_effective_tuition_accrual` selects opt-in MonthlyTuitionReadModel by Enrollment ID; all other Enrollment rows use original TuitionAccrualService.
- Outstanding, Income enrollment picker and TuitionAdjustment refund/credit caps use the same routing.
- Unresolved monthly evidence raises, never displays a deceptively configured 0-VND debt.

## F-02: atomic cancellation/no makeup
- Existing SessionService cancel/update-to-Cancelled rejects a lesson covered by an activated monthly Enrollment.
- Session dialog offers an explicit finance-authorized no-makeup flow.
- `MonthlyTuitionClassCancellationService.cancel_with_no_makeup` updates Session and immutable per-Enrollment billing outcomes in one DB commit. Partial failures roll back. Retry does not double waive.
- Original plan/session ID allocation, rather than mutable Session date, determines waived VND.
- Student absence and rescheduled makeup do not create an Income or additional billing allocation.

## F-03: one/month or three/month Tuition Income
- Read-only quote computes remaining original Session allocations for exact Enrollment; a three-month request requires all three activated plans.
- Operator previews month/quarter before posting. One `IncomeService.create_income` call creates **one genuine receipt**. Payment-period tag identifies quote; it does not modify the canonical accounting period derived from payment date.
- Backend recalculates/validates price within posting transaction; rejects overlapping ACTIVE month/quarter receipt periods (including cross-month quarter overlaps), manual-credit combination and editing amount/period of an already quoted receipt. Voiding an original receipt allows a separately authorized reissue. Existing refund/void procedures remain audited.
- No prepaid accrual is recognized before each original session due date; Income is cash received, not earned revenue.

## F-04: safe opt-in mandatory migration preflight
- Future effective first-of-month only; requires historical Enrollment contract and known Enrollment.start_date.
- `MonthlyTuitionEnrollmentService` rejects opt-in if no trusted verifier is injected; rejects stale/mismatched evidence and all `assess_enrollment_migration` blockers.
- `VerifiedMonthlyTuitionPreflight` checks managed encrypted backup integrity (within 1h), active WRITE authority and trusted reconciliation callback, plus live SQLCipher Enrollment evidence.
- `MonthlyTuitionEnrollmentService.from_verified_backup(...)` composes a trusted runtime verifier with managed backup path and conservative canonical reconciliation checks (duplicate Enrollment, freeze, transfer, adjustment history). This is available to rollout orchestration, but the live monthly plan UI stays gated until full acceptance; never replace evidence with a boolean UI checkbox.

## Remaining cross-group release gates
- Explicit production SQLCipher backup/restore evidence, confirmed FinancePeriod and 8/9/10 UAT, archive/transfer/multi-client crash scenarios, finance reconciliation, open UI and packaging remain under Group B/release acceptance, not a Group A CI shortcut.
- Do not close master #615 solely because this Group A PR passes CI.
