# TUITION-FIX-01 — Zero VND tuition and full non-cash waiver

## Scope and domain contract

The system distinguishes **contracted tuition**, **real money received**, and **non-cash tuition settlement**. A free Enrollment is a configured `agreed_course_fee=0` (not the absence of a tuition contract). A scholarship/discount at Enrollment time may reduce `net_course_fee` to zero. Neither case requires a fabricated Income of 0 VND.

For a tuition Enrollment with accrued tuition that is waived **at collection time** with no cash received, the existing Income form may now accept **Số tiền thực nhận = 0**, only when `Tuition` is selected and the optional non-cash tuition credit checkbox is enabled. A positive credit and an explicit reason are mandatory.

## Implementation

- Standard Income creation still requires positive real received money; amount <= 0 remains invalid in IncomeService. Refunds follow their separate authorized negative Income workflow.
- The form's 0-cash branch uses `IncomeService.create_tuition_credit_only`. It authenticates Student/Class/Enrollment identity before delegation to `TuitionAdjustmentService.credit_adjustment`.
- AdjustmentService applies permission checks, WRITE mutation authority, immutable ledger creation, Finance Period closure validation, audit/outbox, transaction commit, and FinanceDataChanged. No `Income` or `CASH/BANK` movement is created.
- Same dialog keeps one stable idempotency key across UI save retries. No receipt voucher is attached to a fictitious Income.
- Student/Outstanding tuition settlement already includes `TuitionAdjustment.KIND_CREDIT` as non-cash settlement; Finance cash collection totals remain unaffected.
- Zero gross course fee / 100% Enrollment discount are supported by the existing Enrollment pricing snapshot; this change does not modify Enrollment calculations.

## Safety / limitations

- Credit-only grant is a positive financial adjustment: do not create it for an already-zero contract simply to record a free course. Use Enrollment pricing instead.
- The account must have finance.income.create and authorized WRITE; period closing rules still apply.
- The dedicated zero-cash credit-only path enforces a **server-side cap to accrued unpaid tuition** after acquiring the adjustment command lock. Non-cash waiver cannot create excess prepaid credit; unconfigured contracts fail closed. Staff must still verify the intended course and waiver approval.
- Legacy payment-time credits are immutable and may require manual reconciliation on later Income void/edit. TUITION-FIX-01 does not change that ledger lifecycle.
- Repeated credit-only submissions with the **same** idempotency key are deduplicated, but separate dialogs represent separate authorized commands. The operator must check prior adjustments in Tuition Detail.

## UAT matrix

| Case | Expected |
| --- | --- |
| Enrollment course_fee 0 | Explicitly configured tuition contract; accrued 0, no Income needed |
| Enrollment 100% discount | Net tuition 0 and no Income needed |
| Tuition 0 received + credit > 0 + reason | One non-cash adjustment, zero new Income, course balance reduces |
| Tuition 0 received + no credit / no reason | Validation error; nothing committed |
| Book/Other Income 0 | Rejected |
| EDIT existing Income to 0 | Rejected |
| Tuition positive cash + optional positive credit | Existing atomic Income + credit flow preserved |
| Credit-only save retries with same key | Same adjustment; no duplicate |
| Closed finance period or missing WRITE | Rejected, no adjustment |
| Refresh Student Finance / Outstanding | Non-cash credit reflected in settled tuition; real cash dashboard unchanged |

Run Windows CI and actual Windows EXE UAT before merging.
