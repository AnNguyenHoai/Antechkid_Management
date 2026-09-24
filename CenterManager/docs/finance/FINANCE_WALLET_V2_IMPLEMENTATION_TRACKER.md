# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** This file supersedes `FINANCE_WALLET_V2_IMPLEMENTATION_PLAN.md` wherever that older plan conflicts with `FINANCE_WALLET_V2_DOMAIN_SPEC.md`.

## Metadata

| Field | Value |
|---|---|
| Original baseline | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Current implementation base | `main_repos@44b6fb730b516b2eaa61fa29bc87ac7699aa7570` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-06 — Wallet Accounting` |
| Current task | `FW2-06 implementation / full regression` |
| Last completed | `FW2-05 — Settlement Lifecycle` |
| Last updated | `2026-09-24` |

Legend: `[ ] TODO` · `[>] CURRENT` · `[~] IN PROGRESS` · `[x] DONE` · `[!] BLOCKED`.

## Domain guardrails

1. Canonical accounting bucket is the existing **FinancePeriod resolved to exact inclusive bounds**; it is not necessarily a calendar month.
2. Do not create a parallel `FinanceWalletPeriod` table.
3. Mid-month anchors and `duration_months > 1` are valid.
4. Resolved buckets are clamped to configuration effective bounds so transitions cannot overlap.
5. Every realized Income/Expense must resolve to exactly one covering FinancePeriod before persistence succeeds.
6. Future ACTIVE Income and future COMPLETED Expense are prohibited; planned money is not realized money.
7. `Settlement.CONFIRMED` closes the resolved FinancePeriod ledger. `FinancePeriod.status` remains configuration lifecycle only.
8. `Class.fee` is per student per canonical FinancePeriod and is not automatically multiplied by duration.
9. Services are authoritative for authorization/domain state; UI projects those rules.
10. Historical data must never be silently reclassified when period resolution is ambiguous.
11. Financial totals must use complete aggregation and must never depend on arbitrary row limits.
12. Wallet V2 has exactly two canonical money locations: `CASH` and `BANK`; unknown aliases are errors, never guesses.

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[x]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[x]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[x]` | FW2-04 | Closed-period service guard |
| `[x]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[>]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[ ]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics |
| `[ ]` | FW2-08 | Canonical period selector + capability/state UI projection |
| `[ ]` | FW2-09 | Backfill/reconciliation/migration exceptions |
| `[ ]` | FW2-10 | Cross-surface regression and production release gate |

## FW2-01 — Canonical FinancePeriod Foundation — `[x] DONE`

- [x] existing FinancePeriod retained; no parallel Wallet-period table;
- [x] canonical `ResolvedFinancePeriod` implemented;
- [x] mid-month, duration > 1, leap/end-of-month and transition clamping covered;
- [x] runtime suite reported green.

## FW2-02 — Expense Period Assignment — `[x] DONE`

- [x] nullable `Expense.finance_period_id` compatibility FK;
- [x] unique covering period required for COMPLETED Expense;
- [x] future COMPLETED rejected; PENDING remains non-realized;
- [x] assignment recomputed on date/status change;
- [x] ambiguous coverage fails explicitly;
- [x] post-commit projections are best-effort;
- [x] full pytest rerun reported green.

## FW2-03 — Income Period & Realized Semantics — `[x] DONE`

- [x] canonical `Income.finance_period_id` compatibility FK;
- [x] unique covering period required for ACTIVE Income;
- [x] future ACTIVE Income rejected;
- [x] application clock used for realized semantics;
- [x] VOIDED/deleted Income excluded;
- [x] enrollment validated at transaction date;
- [x] post-commit false-failure boundary fixed;
- [x] full Windows pytest reported green.

## FW2-04 — Closed-period Guard — `[x] DONE`

Merged as `main_repos@c8dbbeebbc9b6227f722e6f9611c839d8ecea1d1` after owner-reported green full pytest.

- [x] central `FinanceLedgerGuard` derives closure from `FinancialSettlement.STATUS_CONFIRMED`;
- [x] Income create/update/void/delete guarded;
- [x] realized Expense create/update/delete guarded;
- [x] period moves protect both source and destination ledgers;
- [x] PENDING Expense remains editable because it is non-realized;
- [x] public FinancePeriod mutability APIs available to maintenance/reconciliation;
- [x] business-date guards use the application clock;
- [x] full regression reported PASS on 2026-09-24.

## FW2-05 — Settlement Lifecycle — `[x] DONE`

Merged as `main_repos@44b6fb730b516b2eaa61fa29bc87ac7699aa7570` after GitHub Actions **Pytest Suite #174 SUCCESS** on 2026-09-24.

- [x] Settlement resolves the same unique/clamped canonical FinancePeriod contract as FW2-01;
- [x] confirmation recalculates complete live Income/Expense activity in the confirmation transaction;
- [x] expected Cash/Bank closing calculated as opening + realized income - realized expense;
- [x] actual Cash/Bank are mandatory for confirmation;
- [x] differences are calculated as actual - expected;
- [x] non-zero difference requires a comment;
- [x] confirmation snapshot + `CONFIRMED` status + audit record are persisted atomically;
- [x] confirmation failure before commit cannot close the ledger;
- [x] explicit Admin `reopen()` command requires a reason and writes an audit record in the same transaction;
- [x] reopen transitions `CONFIRMED -> DRAFT`, which reopens the ledger through the existing FW2-04 guard without introducing another period state;
- [x] reopen audit captures period identity, settlement identity, actor through AuditService, previous status/timestamp, reason and reopen timestamp;
- [x] arbitrary row-limit aggregation removed in favor of SQL grouped sums;
- [x] Settlement date defaults use application `Clock`;
- [x] repository-owned flush preserves the service persistence boundary;
- [x] Settlement states `realized_only=True` explicitly at its aggregation boundary;
- [x] full GitHub Actions regression passed.

## FW2-06 — Wallet Accounting — `[>] CURRENT`

### Implemented on `finance-wallet-v2-fw2-06`

- [x] canonical Wallet enum defines exactly `CASH` / `BANK`;
- [x] one centralized resolver maps canonical values plus approved legacy aliases;
- [x] Income create/update payment-method validation normalizes known aliases to canonical persistence values;
- [x] Expense create/update payment-method validation normalizes known aliases to canonical persistence values;
- [x] unknown new-write aliases are rejected instead of stored as guessed Wallets;
- [x] Income/Expense repository filters treat canonical and legacy aliases as equivalent for read compatibility;
- [x] raw unknown historical values remain directly filterable for diagnostics/migration rather than being reclassified;
- [x] `WalletBalanceDTO` / `WalletPeriodSummaryDTO` expose per-Wallet opening, realized income, realized expense, expected closing and net movement;
- [x] `WalletService` performs complete uncapped SQL-backed Cash/Bank aggregation;
- [x] unknown historical Wallet alias causes live accounting/reconciliation to fail explicitly instead of silently dropping money;
- [x] Settlement consumes the same WalletService mapping/aggregation contract;
- [x] Settlement keeps `realized_only=True` explicit to preserve FW2-05 regression/ownership boundary;
- [x] focused FW2-06 regression tests added for aliases, canonical writes, balance equations, repository compatibility and unknown-alias failure.

### Remaining before DONE

- [>] full GitHub Actions pytest suite;
- [ ] audit any regression failure;
- [ ] mark FW2-06 DONE only after green full suite and review.

## FW2-07 — Outstanding / Tuition Obligation

- [ ] `Class.fee` once per billable enrollment per canonical FinancePeriod;
- [ ] no multiplication by `duration_months`;
- [ ] enrollment overlap determines billability;
- [ ] qualifying ACTIVE tuition Income reduces obligation;
- [ ] historical fee source prevents retroactive rewrite.

## FW2-08 — UI Integration

- [ ] selector uses actual FinancePeriod bounds;
- [ ] selected period preserved across Finance surfaces;
- [ ] export uses same period context;
- [ ] fine-grained capability projection;
- [ ] closed period disables normal mutation controls while service guard remains authoritative.

## FW2-09 — Backfill & Reconciliation

- [ ] Income/Expense deterministic assignment backfilled;
- [ ] unresolved/ambiguous rows reported;
- [ ] idempotent rerun;
- [ ] confirmed periods cannot be silently mutated by reconciliation;
- [ ] historical Settlement snapshots preserved.

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
| 2026-09-23 | Existing FinancePeriod remains canonical; no `FinanceWalletPeriod`. | FINAL |
| 2026-09-23 | Resolved bucket is clamped to configuration effective bounds. | FINAL |
| 2026-09-23 | Settlement confirmation owns ledger closure; FinancePeriod.status is configuration lifecycle. | FINAL |
| 2026-09-23 | Class.fee is per canonical FinancePeriod. | FINAL |
| 2026-09-23 | Future realized postings are rejected. | FINAL |
| 2026-09-24 | Closed-period moves protect both source and destination periods. | FINAL |
| 2026-09-24 | PENDING Expense is non-realized. | FINAL |
| 2026-09-24 | Business-date defaults use the application clock. | FINAL |
| 2026-09-24 | Settlement confirmation and its audit record are one atomic transaction. | FINAL |
| 2026-09-24 | Reopen is an explicit Admin `CONFIRMED -> DRAFT` command with mandatory reason and audit; no parallel ledger-open state is introduced. | FINAL |
| 2026-09-24 | Settlement totals use database aggregation, not paged row reads or arbitrary caps. | FINAL |
| 2026-09-24 | Services never call ORM flush directly; settlement identity materialization goes through repository persistence API. | FINAL |
| 2026-09-24 | Settlement makes realized Expense filtering explicit at the service/repository boundary while aggregation remains database-side. | FINAL |
| 2026-09-24 | Wallet V2 canonical persistence values are `CASH` and `BANK`; approved legacy aliases remain readable. | FINAL |
| 2026-09-24 | Unknown Wallet aliases fail live accounting and new-write validation; they are never silently guessed or dropped. | FINAL |
| 2026-09-24 | Settlement consumes the centralized WalletService while retaining explicit realized-ledger ownership. | FINAL |

## Implementation journal

### 2026-09-24 — FW2-06 implementation started

Created `finance-wallet-v2-fw2-06` from merged FW2-05 base `main_repos@44b6fb730b516b2eaa61fa29bc87ac7699aa7570`. Added the canonical `CASH`/`BANK` resolver, Wallet DTOs and WalletService. Income/Expense new writes normalize approved aliases to canonical values while repository filters continue to read canonical and legacy values. Settlement now consumes the same Wallet accounting service, and unknown historical aliases fail reconciliation explicitly rather than disappearing from totals. Focused regression coverage added; full CI pending.

### 2026-09-24 — FW2-05 completed

PR #337 passed GitHub Actions **Pytest Suite #174** and merged into `main_repos@44b6fb730b516b2eaa61fa29bc87ac7699aa7570`. CI audit #1 had previously fixed the service persistence boundary and restored the explicit `realized_only=True` Settlement contract.

### 2026-09-24 — FW2-04 completed

PR #336 closed-period guard passed the full suite as reported by the repository owner and was merged into `main_repos@c8dbbeebbc9b6227f722e6f9611c839d8ecea1d1`.

### 2026-09-24 — FW2-03 completed

PR #335 passed the full Windows pytest suite and was merged. Audit fixes included migration-chain guard, deterministic application clock usage and removal of residual post-commit ClassService lookup.

### 2026-09-23 — FW2-02 completed

Expense canonical assignment, future-realized validation, migration `1e10a026`, best-effort post-commit projection and migration regression fix completed; full rerun reported green.

### 2026-09-23 — FW2-01 completed

Canonical resolved-period model and transition clamping completed; runtime regression reported PASS.
