# Finance Phase 0A — verified current state

**Baseline:** `main_repos@5d1ede131f8e64efa31a3307cff8d590c1b4f23f` (2026-10-30). This is a source audit, not a reconciliation of production data or an EXE release attestation. Source paths below are relative to `CenterManager/`.

## Authority and scope

`docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` governs accounting, Wallet and Settlement. Its tuition-per-FinancePeriod sections were **superseded** by the approved `FINANCE_WALLET_V2_TUITION_BOUNDARY.md`: FinancePeriod is accounting time; tuition is based on the Enrollment contract, billable Sessions and Tuition Accrual. The older `docs/FINANCE_1_1_DATA_INTEGRITY_OUTSTANDING_CONTRACT.md` and 2026-09-23 audits are historical evidence, not current tuition policy. Do not encode their per-class or per-period fee formulas in new diagnostics.

This phase reads models, services, repositories, migrations and representative tests. It adds no detector, UI, schema change, remediation or production data access. See `FINANCE_INTEGRITY_FINDINGS.md` for open risks and `FINANCE_DIAGNOSTICS_RULE_CATALOG.md` for the subsequent implementation gate.

## Source-of-truth matrix

| Entity / derived value | Source of truth | Read path | Write / audit path | Boundary / risk |
|---|---|---|---|---|
| Accounting period | `models/finance_period.py`; effective definitions | `finance_period_service.py`, `finance_ledger_guard.py`; `finance_period_repository.py` | `FinancePeriodService.configure/deactivate`, admin capability | Historical configuration changes can disagree with persisted Income classification; see F-21. |
| Realized receipt | `models/income.py`: ACTIVE, not deleted, payment date, amount, Wallet method and period | `income_repository.py` aggregate/list; `wallet_service.py` | `income_service.py` create/update/void/delete; audit log in transaction, timeline best effort | `Float` amount; legacy unattributed Tuition; active soft-delete path; Dashboard cap. |
| Realized outflow | `models/expense.py`: COMPLETED/legacy Paid, not deleted | `expense_repository.py` realized aggregates; Wallet | `expense_service.py`; audit and expense timeline | Pending is not cash outflow; `Float` amount; Dashboard cap. |
| Tuition contract | `models/enrollment.py`: tuition snapshot, discount, status, lineage | `enrollment_repository.py` | `enrollment_service.py`, transfer/reconciliation services and audit | An Enrollment, not a student/class pair or FinancePeriod, owns one tuition balance. |
| Accrued tuition | Enrollment snapshot + billable Session/attendance policy | `tuition_accrual_service.py`, `tuition_policy.py` | Derived, no accrual ledger row | A period filter is report context and must not price the academic contract. Unresolved legacy contract is not zero debt. |
| OWED / PREPAID | Accrual minus ACTIVE Tuition payments for exact Enrollment | `outstanding_service.py`, `income_repository.py:sum_active_tuition_for_enrollment`, `dto/outstanding_dto.py` | Derived; payment/adjustment writes elsewhere | Preserve signed balance by Enrollment; do not net across students or enrollments. |
| Refund / credit | `models/tuition_adjustment.py`, origin IDs, kind and idempotency key | `tuition_adjustment_repository.py`, Tuition Detail / Outstanding | `tuition_adjustment_service.py`; financial guard and audit | Refund may move Wallet, credit may not; inspect kind and origin before aggregating. |
| Settlement | `models/financial_settlement.py`, actual and expected Cash/Bank | `financial_settlement_service.py` via `wallet_service.py` complete repository aggregates | Draft/confirm/reopen with capabilities and audit | Confirmed closes ledger; difference can be permitted with comment, so nonzero alone is not corruption. |
| Dashboard | Projection, not ledger | `finance_dashboard_service.py`, Finance workspace UI | None | Period totals use first-page limits of 10,000, unlike Wallet/Settlement aggregation. |

`repositories/provider.py` supplies persistence boundaries. `models/audit_log.py` is the durable audit record. Finance UI is under `ui/finance_workspace/`; controls are a permission projection, while services enforce mutation rights. Migration lineage includes `migrations/versions/1e10a018_finance_period.py`, `1e10a021_financial_settlement.py`, `1e10a026_expense_finance_period.py`, `1e10a027_add_income_finance_period_id.py`, `1e10a028_class_fee_history.py`, and `1e10a032_income_enrollment_attribution.py`. Check the current migration head again before any later schema PR.

## Verified behavior and limits

- `FinancePeriodDefinition.resolved_for_configuration` clamps a period to configuration bounds; `IncomeService` resolves posting period and guards a closed period. For Tuition it resolves an exact Enrollment without requiring current ACTIVE status, allowing old debt collection.
- `IncomeRepository` excludes VOIDED and deleted rows from qualifying tuition sums. `OutstandingService` reads the exact Enrollment payment total and calculates accrued tuition from the Enrollment snapshot and sessions. A missing contract is unresolved rather than a confirmed paid amount.
- `WalletService` aggregates complete repository sums by payment method for Settlement. It fails on unknown Wallet aliases; `FinancialSettlementService` requires capability and records confirm/reopen actions. Dashboard currently groups unknown aliases under `Other` instead, a divergence recorded as NEW-01.
- `IncomeService` and `ExpenseService` catch post-commit timeline projection failures. Primary finance audit records are written in the mutation transaction. Timeline failure is still observable in logs, but it no longer makes the committed save appear to fail through that path.
- `Income.amount` and `Expense.amount` are SQLAlchemy `Float`. Tuition adjustments and snapshot monetary fields use Decimal/Numeric. Precision migration requires separate design and historical-data validation.
- There is no bank statement transaction model or per-line reconciliation workflow in the inspected source. Wallet/Settlement compares internal activity and entered actual balances; it does not prove individual bank movements.

## Release boundary

The signed database identity incident (`docs/incidents/2026-10-28-signed-db-identity-recovery.md`) and cross-machine key provisioning are separate operational gates. Existing test `tests/test_cross_machine_database_key_provisioning.py` proves the provisioning contract with a fake store; `docs/EP-PROD-06_BACKUP_RESTORE_DISASTER_RECOVERY_UAT.md` explicitly requires physical Windows recovery evidence. CI and this audit do not prove that the deployed EXE contains the current source or that a new machine can restore the real workspace.
