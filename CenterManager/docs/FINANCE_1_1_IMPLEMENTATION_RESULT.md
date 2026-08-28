# FINANCE-1.1 — Implementation Result

## Implemented

1. Tuition balance is calculated only for real Enrollment pairs.
2. Expected tuition is sourced from Class.fee.
3. Only Income with income_type == Tuition is counted as tuition paid.
4. Missing/zero class fee is exposed explicitly as `No Tuition Configured`.
5. Missing fee is no longer silently omitted from outstanding results.
6. Student summaries expose `has_unconfigured_tuition`.
7. Aggregate debt arithmetic excludes unconfigured classes rather than treating them as paid.
8. Outstanding UI can filter `No Tuition Configured`.
9. Student Financial widget shows `Chưa cấu hình học phí` when tuition configuration is incomplete.
10. Added regression tests for the Finance-1.1 contract.

## Deferred intentionally

No new TuitionObligation table was introduced. The current Enrollment + Class.fee +
Tuition Income model remains the source of truth until requirements require discounts,
refunds, installments or cross-class payment allocation.
