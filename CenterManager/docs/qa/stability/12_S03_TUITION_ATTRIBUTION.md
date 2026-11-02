# QA-S03 R1 — Enrollment attribution and tuition as-of

**Baseline:** `main_repos` `59fc7ecb14f9c59094904e08e886834d3ad5d121` (merged PR #544). Prior PR SHA `8008cf479c71eee06f66f4944d06064788418142`: [CI #880 PASS](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41477670063).

**Domain basis:** `docs/finance/FINANCE_INVARIANTS.md` rules I05 (exact enrollment), I06 (non-tuition/unattributed do not settle tuition), I07 (historic debt/receipts remain), and as-of separation.

## Added regression
`test_qa_stability_s03_tuition_attribution.py` creates one student with two distinct enrollments, January and March tuition receipts for first enrollment, February tuition receipt for second, plus non-tuition, voided and legacy-unattributed Tuition income. Query `IncomeRepository.sum_active_tuition_for_enrollment` at two historical cutoff dates.

Expected receipts: first enrollment 100 through February, 140 through March; second enrollment 70. Legacy-unattributed and other/voided payments must not contaminate the tuition contract.

Run: `cd CenterManager && python -m pytest tests/test_qa_stability_s03_tuition_attribution.py -v`.

**At authoring:** new test NOT RUN; exact-head CI required. Scope is repository ledger attribution only: it does NOT establish accrued tuition obligation, archive/withdraw UI, refunds, or financial reports correctness. Those need separate scenarios; no repair or reclassification of historical records is authorized. No production source changed.
