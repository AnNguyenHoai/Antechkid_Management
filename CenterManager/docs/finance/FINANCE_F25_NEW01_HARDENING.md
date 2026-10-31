# F-25 / NEW-01 — Finance Dashboard correctness hardening

**Scope:** source-level fix on a dedicated branch from `main_repos`. No production database was read or altered, no migration, no historical amount correction.

## Before and after

| Path | Before | After |
|---|---|---|
| Period payment-method revenue/expense | First 10,000 ORM rows of an arbitrarily larger set; ignored total count. | One SQL `GROUP BY payment_method` for complete ACTIVE, nondeleted Income or realized, nondeleted Expense within the same reporting bounds. |
| Today/month totals | Same 10,000-row page cap. | Reuse complete grouped read, including canonical wallet validation. |
| Unknown historical wallet method | Dashboard silently reported `Other`; Cash/Bank omitted money. | Dashboard, Wallet and Settlement all fail explicitly through the same WalletService grouped-row interpretation. Finance Dashboard page shows its existing error state, not zero or partial totals. |
| Recent transactions | Intentionally paginated. | Remain paginated; they are previews, not financial totals. |

Income period totals apply both `finance_period_start` and payment-date bounds. Today's/month's cross-period totals use their date bounds without a period filter, as before. Expense period totals apply date bounds and the lower-bound period parameter; only `Completed` and legacy `Paid` are realized. Pending/deleted Expenses and VOIDED/deleted Income do not contribute. Wallet/Settlement read the same aggregate repository methods and resolve aliases through the same WalletService helper. A late old-debt payment on a withdrawn Enrollment in an archived Class still counts in its accounting period.

## Synthetic correctness and performance evidence

Run `QT_QPA_PLATFORM=offscreen python -m pytest -q -s tests/test_finance_phase0a_known_risks.py` from `CenterManager/`. On a local Linux SQLite file fixture (Python 3.12, SQLAlchemy 2.1.6), each scenario inserted 10,001 synthetic transactions and measured the read operation only. One observed run:

| Kind | Old page-one sum / known total | Old list read | New Dashboard total | New aggregate read | Wallet/Settlement |
|---|---:|---:|---:|---:|---:|
| Income | 10,000 / 10,001 | 599.73 ms, 2 SQL reads, 10,000 ORM rows | 10,001 | 9.72 ms, 1 SQL read, grouped row(s) | 10,001.00 |
| Expense | 10,000 / 10,001 | 185.73 ms, 2 SQL reads, 10,000 ORM rows | 10,001 | 6.15 ms, 1 SQL read, grouped row(s) | 10,001.00 |

These timings are a single local sample, not a Windows or production latency guarantee. Regression asserts one `GROUP BY` without `LIMIT` for each Dashboard aggregate and constant query count with 10,001 rows; the grouping cardinality follows the number of distinct payment-method strings, not transaction count. The old page-one path is measured only as a reproducible comparison; Dashboard no longer calls it for totals. Daily and monthly totals in the same test also return 10,001.

## Risk assessment and rollback

| Risk | Control |
|---|---|
| Alias outside canonical Cash/Bank causes the Dashboard to show an error where it previously showed an `Other` amount. | Intentional fail-closed behavior; inspect the existing transaction through authorized finance workflows and resolve the historical alias with a separately reviewed correction. No automatic classification or backfill. |
| SQL grouping over legacy Float may carry a small binary representation artifact. | WalletService applies its existing Decimal-to-cent conversion to grouped values; Dashboard projects the same totals to float for existing UI formatting. No persistence conversion. |
| More distinct legacy method strings could add grouped rows. | One aggregate query per metric; no per-transaction ORM hydration or N+1. Performance test verifies the 10,001-row case. |
| Dashboard period and Wallet scopes drift. | Shared income period start/date bounds, Expense realized status/date bounds, and tests comparing Dashboard, Wallet and Settlement on archived/withdrawn and inactive history. |

Rollback is a revert of this PR's code and test changes on `main_repos`, followed by Windows CI; there is no schema or data rollback. Reversion would restore the known F-25/NEW-01 misreporting and must be treated as a correctness regression. An unknown historical alias requires explicit review rather than disabling the failure path.
