# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** This file supersedes the earlier `FINANCE_WALLET_V2_IMPLEMENTATION_PLAN.md` wherever that file conflicts with `FINANCE_WALLET_V2_DOMAIN_SPEC.md` or `FW2_01_1_PERIOD_MODEL_RECONCILIATION.md`.

## Metadata

| Field | Value |
|---|---|
| Base | `main_repos@263692c6c5ff8a65c9314b45742e18d0aa052f7d` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-02 — Expense Period Assignment` |
| Current task | `FW2-02 CI rerun after migration-contract regression fix` |
| Last completed | `FW2-01 — Canonical FinancePeriod Foundation` |
| Last updated | `2026-09-23` |

Legend: `[ ] TODO` · `[>] CURRENT` · `[~] IN PROGRESS` · `[x] DONE` · `[!] BLOCKED` · `[-] SKIPPED`.

## Domain guardrails

1. Canonical accounting bucket is the **existing FinancePeriod**, resolved to exact inclusive bounds. It is not necessarily a calendar month.
2. Do not create a parallel `FinanceWalletPeriod` calendar-month table.
3. Mid-month anchors and `duration_months > 1` remain valid domain behavior.
4. Canonical resolver clamps a natural bucket to the owning configuration effective range so transitions cannot overlap.
5. Every realized Income/Expense must resolve to exactly one covering FinancePeriod before persistence succeeds.
6. Future ACTIVE Income and future COMPLETED Expense are prohibited. Planned money is not realized ledger money.
7. `Settlement.CONFIRMED` closes the resolved FinancePeriod ledger for normal mutation. Do not overload `FinancePeriod.status` with OPEN/FINALIZED.
8. `Class.fee` is the per-student tuition charge for **one canonical FinancePeriod**, not automatically monthly and not multiplied by `duration_months`.
9. Fine-grained Finance capability + WRITE mode + domain-state precondition govern mutation UI; services remain authoritative.
10. Historical data must never be silently reclassified when resolution is ambiguous.

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[>]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[ ]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[ ]` | FW2-04 | Closed-period service guard |
| `[ ]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[ ]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[ ]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics |
| `[ ]` | FW2-08 | Canonical period selector + capability/state UI projection |
| `[ ]` | FW2-09 | Backfill/reconciliation/migration exceptions |
| `[ ]` | FW2-10 | Cross-surface regression and production release gate |

## FW2-01 — Canonical FinancePeriod Foundation — `[x] DONE`

### `[x] FW2-01.1` Persistence/domain reconciliation
Existing `FinancePeriod` retained; no parallel Wallet-period table.

### `[x] FW2-01.2` Canonical resolved-period resolver
`ResolvedFinancePeriod` + effective-range-clamped resolution implemented. Normal, mid-month, multi-month, leap/end-of-month and transition semantics covered.

### `[x] FW2-01.3` Runtime regression tests
Runtime pytest reported PASS by repository owner on 2026-09-23.

### `[x] FW2-01.4` Phase review
- [x] exact selected bounds available through `FinancePeriodService.resolve_period()`;
- [x] canonical identity no longer requires Month/Year inference;
- [x] F-20 transition overlap closed by clamping;
- [x] FW2-01 runtime tests green.

## FW2-02 — Expense Period Assignment — `[>] CURRENT`

### Implemented

- [x] add nullable `Expense.finance_period_id` FK bridge; nullable preserves legacy rows until FW2-09 reconciliation;
- [x] Alembic `1e10a026` migration from repository head `1e10a025`;
- [x] require unique covering FinancePeriod for new/updated COMPLETED Expense;
- [x] reject future COMPLETED Expense;
- [x] allow future PENDING as non-realized;
- [x] recompute assignment from final date/status on update;
- [x] ambiguous overlapping configurations fail explicitly instead of silently choosing one;
- [x] missing period fails realized posting;
- [x] post-commit timeline/event failures are best-effort and no longer report committed money mutation as failed;
- [x] focused rule regressions added.

### Runtime evidence

GitHub Actions `Pytest Suite #159` on merged PR #333 / `main_repos@263692c6c5ff8a65c9314b45742e18d0aa052f7d` executed 1,923 tests:

- [x] all FW2-01 resolver tests passed;
- [x] all FW2-02 Expense assignment tests passed;
- [x] FinancePeriod repository round-trip passed;
- [x] Alembic migration upgrade/downgrade integration tests passed;
- [x] 1,919 tests passed and 3 skipped;
- [!] exactly one test failed: `test_finance_period_migrations_use_unique_revisions_and_current_chain` because its hard-coded finance-migration filename list predated `1e10a026_expense_finance_period.py`.

The failure was a stale test contract, not a production migration or FW2-02 domain failure. The fix keeps the strict migration inventory check and adds `1e10a026` plus its expected `down_revision = "1e10a025"`; production behavior was intentionally not relaxed.

### Remaining before phase closure

- [x] audit full failed run and isolate root cause;
- [x] fix stale migration revision contract on `finance-wallet-v2-fw2-02-ci-fix`;
- [>] rerun full pytest after the test-contract fix;
- [ ] mark FW2-02 DONE only after green rerun;
- [ ] leave bulk legacy deterministic backfill to FW2-09 as planned.

## FW2-03 — Income Period & Realized Semantics

- [ ] require unique covering FinancePeriod for ACTIVE Income;
- [ ] reject future ACTIVE Income on create/update;
- [ ] VOIDED excluded from live ledger;
- [ ] recompute canonical assignment when payment date changes;
- [ ] date-aware enrollment validation;
- [ ] fix post-commit false-failure boundary;
- [ ] runtime regressions.

## FW2-04 — Closed-period Guard

- [ ] central guard derives closure from confirmed Settlement for selected resolved period;
- [ ] Income create/update/void/delete guarded;
- [ ] realized Expense create/update/delete guarded;
- [ ] moving transactions into/out of closed period guarded;
- [ ] maintenance/backfill cannot silently bypass closure;
- [ ] runtime regressions.

## FW2-05 — Settlement Lifecycle

- [ ] confirmation recalculates live ledger;
- [ ] expected Cash/Bank closing calculated;
- [ ] actual Cash/Bank required;
- [ ] differences calculated;
- [ ] configured non-zero difference requires comment;
- [ ] confirmation snapshot atomic;
- [ ] confirmed period closes only after successful transaction;
- [ ] explicit Admin reopen workflow if implemented;
- [ ] remove aggregation caps;
- [ ] runtime regressions.

## FW2-06 — Wallet Accounting

- [ ] canonical wallets `CASH` / `BANK`;
- [ ] legacy aliases normalized safely;
- [ ] unknown wallet aliases reported, never guessed;
- [ ] opening + income - expense = expected closing;
- [ ] Settlement difference = actual - expected;
- [ ] no arbitrary row-limit totals;
- [ ] reserve transfer semantics without modeling transfers as fake Income/Expense.

## FW2-07 — Outstanding / Tuition Obligation

- [ ] `Class.fee` applied once per billable enrollment per canonical FinancePeriod;
- [ ] no automatic multiplication by `duration_months`;
- [ ] enrollment overlap determines billability;
- [ ] ACTIVE qualifying tuition Income reduces obligation;
- [ ] Not Yet / Partial / Paid / Overpaid / No Tuition Configured semantics;
- [ ] define historical fee source so changing current Class.fee does not silently rewrite finalized history.

## FW2-08 — UI Integration

- [ ] selector uses actual FinancePeriod bounds, not Month/Year inference;
- [ ] selected period preserved across Dashboard/Income/Expense/Outstanding/Settlement;
- [ ] export uses same period context;
- [ ] capability projection matches service capability;
- [ ] closed period disables normal mutation controls;
- [ ] service remains authoritative.

## FW2-09 — Backfill & Reconciliation

- [ ] Income compatibility assignment reconciled;
- [ ] Expense deterministic assignment backfilled;
- [ ] unresolved/ambiguous rows reported;
- [ ] idempotent rerun;
- [ ] historical Settlement snapshots preserved;
- [ ] no silent retroactive reclassification;
- [ ] reconciliation metrics recorded.

## FW2-10 — Production Gate

- [ ] cross-surface totals agree;
- [ ] period transition tests pass;
- [ ] future posting tests pass;
- [ ] closure/reopen tests pass;
- [ ] capability matrix tests pass;
- [ ] high-volume totals prove no truncation;
- [ ] legacy compatibility tests pass;
- [ ] final Finance audit completed.

## Decision log

| Date | Decision | Status |
|---|---|---|
| 2026-09-23 | Existing `FinancePeriod` remains the canonical period domain. | FINAL |
| 2026-09-23 | Do not create `FinanceWalletPeriod`. | FINAL |
| 2026-09-23 | Resolved bucket is clamped to configuration effective bounds. | FINAL |
| 2026-09-23 | Settlement confirmation owns ledger closure; `FinancePeriod.status` remains configuration lifecycle. | FINAL |
| 2026-09-23 | `Class.fee` is per canonical FinancePeriod, not per calendar month. | FINAL |
| 2026-09-23 | Future realized postings are rejected, not treated as planned actuals. | FINAL |
| 2026-09-23 | Expense FK remains nullable during rollout; service requires it for new realized postings, FW2-09 owns legacy reconciliation. | FINAL |
| 2026-09-23 | Ambiguous period coverage is a hard validation failure for new realized postings. | FINAL |
| 2026-09-23 | CI fix updates the strict migration revision contract; it must not weaken FW2-02 posting invariants to make tests green. | FINAL |

## Implementation journal

### 2026-09-23 — FW2-02 CI failure audited and fixed

PR #333 merged to `main_repos@263692c6c5ff8a65c9314b45742e18d0aa052f7d`. Pytest Suite #159 completed with `1 failed, 1919 passed, 3 skipped`. The only failure was the legacy strict filename inventory in `test_finance_period_migration_revision.py`, which did not include the intentionally added `1e10a026_expense_finance_period.py`. All FW2-01, FW2-02, FinancePeriod repository, and migration upgrade/downgrade runtime tests passed. Created `finance-wallet-v2-fw2-02-ci-fix`; updated the migration contract to include revision `1e10a026` chained from global head `1e10a025`. Awaiting green full-suite rerun before closing FW2-02.

### 2026-09-23 — FW2-02 implementation merged

Base was `main_repos@30f7ccd38adca90f2b67dfbd4dc75ad2e64265d4`. FW2-02 added Expense period FK/migration, deterministic unique-period assignment, future-realized guard, reassignment on date/status change, best-effort post-commit projections, and focused regressions. PR #333 merged into main_repos.

### 2026-09-23 — FW2-01 completed

FW2-01.1 reconciliation, FW2-01.2 resolver, and FW2-01.3 runtime regression were completed. Owner reported pytest PASS. Phase review confirms exact canonical bounds are available and F-20 is closed.
