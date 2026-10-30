# Finance Phase 0A — invariants and diagnostic boundaries

Baseline: `main_repos@5d1ede1`. These are approved domain rules or verified current contracts, not permission to repair historical records. See `FINANCE_CURRENT_STATE_AUDIT.md` for governing specifications.

| ID | Invariant | Evidence / interpretation |
|---|---|---|
| I01 | A realized Income or Expense posts to one canonical accounting period and one known CASH/BANK Wallet. | `finance_ledger_guard.py`, `wallet_service.py`, Income/Expense services; exception handling for ambiguous legacy rows must be explicit. |
| I02 | ACTIVE, nondeleted Income adds to realized receipts. VOIDED or deleted Income does not. Only completed/legacy Paid nondeleted Expense reduces Wallet. | `income_repository.py`, `expense_repository.py`, Wallet V2 spec. Pending Expense is not cash paid. |
| I03 | Confirmed Settlement closes normal realized-ledger mutation for that period; reopen requires the established admin capability, reason and audit. | `financial_settlement_service.py`, `finance_ledger_guard.py`. A nonzero explained difference may be valid. |
| I04 | Tuition obligation is determined by one Enrollment snapshot and billable sessions as of a date; accounting-period duration does not create or price tuition. | Approved `FINANCE_WALLET_V2_TUITION_BOUNDARY.md`, `tuition_accrual_service.py`. Earlier per-period `Class.fee` rule is superseded. |
| I05 | For each exact Enrollment: signed balance = accrued tuition minus qualifying ACTIVE tuition receipts and adjustments according to their kind. Positive is OWED; negative is PREPAID. | `outstanding_service.py`, `income_repository.py`, tuition adjustment and DTO contracts. Keep both totals separately; never net across enrollments or students. |
| I06 | Non-Tuition Income never pays an Enrollment's tuition; a legacy Tuition Income without enrollment attribution is unresolved, not safely assigned by date alone. | `models/income.py`, `income_service.py:list_unattributed_tuition`, reconciliation service. Multiple historical enrollments require explicit selection. |
| I07 | Archive/withdrawal retains history, old debt and prepaid credit; it does not automatically refund or transfer money. | Archive/tuition regression tests and `income_service.py:search_tuition_enrollment_choices`. |
| I08 | Refund, credit and transfer must preserve origin, reason, authorization and idempotency where applicable; a credit without Wallet movement must not be counted as new bank/cash receipt. | `tuition_adjustment_service.py`, `enrollment_transfer_service.py`. Exact financial effects must be selected by adjustment kind. |
| I09 | Financial totals are complete regardless of record count. UI paging must not truncate an aggregate. | `AGENTS.md` and Wallet V2 spec. Current Dashboard violates this above 10,000 matching rows; see F-25. |
| I10 | A diagnostic read must not flush, commit, repair, reclassify or change a financial row. An error is distinct from an empty result. | Phase 0B contract; data-source exceptions must remain visible to the reviewer. |

## Accounting versus academic dates

Payment date determines posting period and Wallet movement. A Tuition payment's Enrollment attribution determines which tuition contract it settles; an old debt payment may occur after withdrawal or archive. As-of date bounds the accrual and qualifying payments for a historical balance. Diagnostics must expose these dates separately rather than reject a legitimate late payment because its payment date is outside the enrollment's active teaching dates.

## Historical uncertainty

Missing Enrollment contract, ambiguous legacy attribution, period classification after a retroactive configuration change and unknown Wallet aliases are **unresolved evidence**, not zero balances or guessed mappings. Any future backfill requires its own reviewed policy and provenance. A detector may flag an exception but may not silently choose the historical meaning.
