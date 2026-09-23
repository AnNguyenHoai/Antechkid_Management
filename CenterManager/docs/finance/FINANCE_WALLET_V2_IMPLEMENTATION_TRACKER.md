# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** This file supersedes the earlier `FINANCE_WALLET_V2_IMPLEMENTATION_PLAN.md` wherever that file conflicts with `FINANCE_WALLET_V2_DOMAIN_SPEC.md` or `FW2_01_1_PERIOD_MODEL_RECONCILIATION.md`.

## Metadata

| Field | Value |
|---|---|
| Base | `main_repos@30f7ccd38adca90f2b67dfbd4dc75ad2e64265d4` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-02 — Expense Period Assignment` |
| Current task | `FW2-02 runtime verification / reconciliation follow-up` |
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

### Implemented on `finance-wallet-v2-fw2-02`

- [x] add nullable `Expense.finance_period_id` FK bridge; nullable preserves legacy rows until FW2-09 reconciliation;
- [x] Alembic `1e10a026` migration from current `1e10a025` head;
- [x] require unique covering FinancePeriod for new/updated COMPLETED Expense;
- [x] reject future COMPLETED Expense;
- [x] allow future PENDING as non-realized;
- [x] recompute assignment from final date/status on update;
- [x] ambiguous overlapping configurations fail explicitly instead of silently choosing one;
- [x] missing period fails realized posting;
- [x] post-commit timeline/event failures are best-effort and no longer report committed money mutation as failed;
- [x] focused rule regressions added.

### Remaining before phase closure

- [>] run migration + focused/full pytest on branch;
- [ ] verify repository integration with real SQLite/PostgreSQL test session;
- [ ] leave bulk legacy deterministic backfill to FW2-09 as planned;
- [ ] record runtime evidence and close FW2-02 if green.

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

## Implementation journal

### 2026-09-23 — FW2-02 implementation started from new main base

Base rebased to `main_repos@30f7ccd38adca90f2b67dfbd4dc75ad2e64265d4`, which is merge PR #332 and already contains FW2-01 implementation. Created `finance-wallet-v2-fw2-02`. Added Expense period FK/migration, deterministic unique-period assignment, future-realized guard, reassignment on date/status change, best-effort post-commit projections, and focused regressions. Runtime verification remains before marking FW2-02 DONE.

### 2026-09-23 — FW2-01 completed

FW2-01.1 reconciliation, FW2-01.2 resolver, and FW2-01.3 runtime regression were completed. Owner reported pytest PASS. Phase review confirms exact canonical bounds are available and F-20 is closed.
