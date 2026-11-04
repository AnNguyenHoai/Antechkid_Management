# EP-FIN-11 — Expense Workspace Completion & Finance Closure Audit Report

## A. Repository State

- Base branch: `main_repos`
- Base SHA: `17beaa019f2b3dcc9e39fbbcb5227a91c82519dc`
- Task branch: `ep-fin-11-expense-finance-closure`
- Final SHA: populated by the Git commit containing this report

## B. Expense Audit Before Change

| Area | Before | Gap |
|---|---|---|
| Pagination | UI requested `page=1, per_page=1000` | Not true server paging |
| Filtering | repository supported filters, UI fetched a large batch | Workspace did not use a canonical server page contract |
| Sorting | local list sort | Global result order could differ across pages |
| Export | no Expense CSV export | Missing parity with Income/Outstanding |
| Finance Period | UI date clamp only | Service/repository query did not receive shared period start |
| Status semantics | Pending and Completed both counted as outflow | Dashboard/Settlement accounting defect |
| Audit | ExpenseTimelineService records create/update/delete | Retained |
| Event refresh | FinanceDataChanged on mutations | Retained |

## C. Expense Status Contract

- **Pending:** operational expense record; money has not yet left Cash/Bank. It remains visible in Expense Workspace but is excluded from realized Dashboard totals and Draft Settlement.
- **Completed:** realized expense; contributes to Dashboard expense totals and reduces Cash/Bank in Draft Settlement.
- **Paid:** legacy compatibility state treated as realized so older rows remain financially visible.
- Deleted rows remain excluded.

## D. Production Changes

### `repositories/expense_repository.py`
- Added one shared filtered query.
- Added whitelisted server-side sorting.
- Added Finance Period lower-bound support.
- Added explicit realized-expense filter (`Completed`, legacy `Paid`).

### `services/expense_service.py`
- Added server paging/sorting parameters while preserving existing defaults.
- Added Finance Period query propagation.
- Added full filtered-result UTF-8-SIG CSV export.
- Existing create/update/delete, timeline and FinanceDataChanged behavior retained.

### `ui/finance_workspace/expense_list_page.py`
- Removed the `per_page=1000` browsing workaround.
- Added server pagination, sorting and filtering.
- Added full filtered CSV export.
- Uses the FinanceWorkspaceShell shared period.

### `services/finance_dashboard_service.py`
- Realized Expense totals now exclude Pending.
- Shared Finance Period is forwarded to Expense queries.
- Recent Expense remains an operational list and may show Pending records.

### `services/financial_settlement_service.py`
- Draft Settlement now includes only realized Expense (`Completed` + legacy `Paid`).
- Confirmed Settlement snapshot/immutability behavior is unchanged.

### `ui/finance_workspace/finance_period_config_dialog.py`
- Added minimal UI over the existing effective-dated FinancePeriod service contract.
- Supports list, configure-from-effective-date and deactivate.
- No arbitrary edit/activate lifecycle was invented.

### `ui/finance_workspace/finance_workspace_shell.py`
- Added admin Finance Period configuration entry point.
- Requires `finance.period.manage`/admin and WRITE mode before opening mutation flow.
- Refresh after period configuration uses the same shared-period context across all Finance pages.

## E. Finance Period UI Contract

- UI location: Finance Workspace shared period bar (`⚙ Cấu hình kỳ`).
- Create/change flow: `FinancePeriodService.configure(duration_months, effective_from)`.
- Historical rule handling: effective-dated configuration; older history is retained.
- End flow: `FinancePeriodService.deactivate(...)`.
- Permission: `finance.period.manage` / admin.
- WRITE mode: enforced by Finance Workspace and dialog before mutation.
- Validation: domain/service remains authoritative.

## F. Regression Coverage Added

`tests/test_ep_fin_11_finance_closure.py` locks:

- Python parse gate for every changed Python source.
- Expense server pagination/filter/sort query contract.
- Full filtered CSV export contract.
- Removal of `per_page=1000` Expense browsing workaround.
- Pending-vs-realized semantics in Dashboard and Settlement.
- Finance Period UI usage of the existing service contract.
- Shared-period event refresh contract.
- Student Financial read-only boundary.

Existing EP-FIN-10 regression remains responsible for confirmed Settlement immutability, live Draft behavior and cross-module mutation refresh.

## G. Test Execution Evidence

No local pytest PASS is claimed in this report. The available execution runtime for this implementation does not provide a reliable checkout/execution path for this private GitHub repository. GitHub CI / reviewer execution is authoritative.

Recommended commands from `CenterManager/`:

```bash
pytest tests/test_ep_fin_11_finance_closure.py -q
pytest tests/test_finance_17_event_refresh.py -q
pytest tests/test_ep_fin_10_cross_module_regression.py -q
pytest tests/ -q
```

## H. Migration Evidence

EP-FIN-11 introduces no schema or migration. Existing FinancePeriod, Expense and FinancialSettlement schemas are reused unchanged. The existing project migration suite remains the authoritative old-DB-to-HEAD gate.

## I. Remaining Finance Debt

No additional Finance MVP feature is intentionally introduced by EP-FIN-11. Closure depends on CI/full-suite confirmation of the implementation in this PR.

## Final Status

**PENDING CI / REVIEW — do not claim Finance Workspace PASS until the repository test suite confirms this implementation.**
