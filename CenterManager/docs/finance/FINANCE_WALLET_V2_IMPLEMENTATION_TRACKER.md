# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** This file supersedes `FINANCE_WALLET_V2_IMPLEMENTATION_PLAN.md` wherever that older plan conflicts with `FINANCE_WALLET_V2_DOMAIN_SPEC.md`.

## Metadata

| Field | Value |
|---|---|
| Original baseline | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Current implementation base | `main_repos@71f8b73634e1ad19b9399cf9e00b48e19fb5fd4b` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-04 — Closed-period Guard` |
| Current task | `FW2-04 full regression / audit` |
| Last completed | `FW2-03 — Income Period & Realized Semantics` |
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

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[x]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[x]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[>]` | FW2-04 | Closed-period service guard |
| `[ ]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[ ]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[ ]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics |
| `[ ]` | FW2-08 | Canonical period selector + capability/state UI projection |
| `[ ]` | FW2-09 | Backfill/reconciliation/migration exceptions |
| `[ ]` | FW2-10 | Cross-surface regression and production release gate |

## FW2-01 — Canonical FinancePeriod Foundation — `[x] DONE`

- [x] existing FinancePeriod retained; no parallel Wallet-period table;
- [x] canonical `ResolvedFinancePeriod` implemented;
- [x] mid-month, duration > 1, leap/end-of-month and transition clamping covered;
- [x] owner-reported runtime suite green.

## FW2-02 — Expense Period Assignment — `[x] DONE`

- [x] nullable `Expense.finance_period_id` compatibility FK;
- [x] Alembic `1e10a026`;
- [x] unique covering period required for COMPLETED Expense;
- [x] future COMPLETED Expense rejected;
- [x] PENDING remains non-realized and may be future-dated;
- [x] assignment recomputed on date/status change;
- [x] ambiguous coverage fails explicitly;
- [x] post-commit timeline/event projection is best-effort;
- [x] migration-chain regression guard updated;
- [x] full pytest rerun reported PASS by repository owner.

## FW2-03 — Income Period & Realized Semantics — `[x] DONE`

Merged PR #335 into `main_repos@71f8b73634e1ad19b9399cf9e00b48e19fb5fd4b`.

- [x] canonical `Income.finance_period_id` compatibility FK via Alembic `1e10a027`;
- [x] unique covering FinancePeriod required for ACTIVE Income;
- [x] future ACTIVE Income rejected on create/update;
- [x] application business clock used for posting/realized semantics;
- [x] VOIDED/deleted Income excluded from realized semantics;
- [x] canonical assignment recomputed when payment date changes;
- [x] enrollment validated at transaction date, not current status only;
- [x] post-commit timeline projection cannot turn a committed mutation into a false save failure;
- [x] post-commit ClassService lookup removed;
- [x] migration-chain regression updated through `1e10a027`;
- [x] full Windows pytest reported PASS by repository owner on 2026-09-24.

## FW2-04 — Closed-period Guard — `[>] CURRENT`

### Implemented on `finance-wallet-v2-fw2-04`

- [x] central `FinanceLedgerGuard` derives closure from `FinancialSettlement.STATUS_CONFIRMED`;
- [x] closure identity is resolved canonical `period_start`, not Month/Year and not FinancePeriod configuration status;
- [x] public `FinancePeriodService.ensure_period_is_mutable()` / `is_period_closed()` projection added;
- [x] Income create guarded against closed destination period;
- [x] Income update guards source period and resolved destination period;
- [x] Income void/delete guard current canonical period;
- [x] realized Expense create guarded;
- [x] realized Expense update guards source and destination, including COMPLETED↔PENDING transitions;
- [x] realized Expense delete guarded;
- [x] PENDING Expense remains editable because it is non-realized ledger data;
- [x] Expense future-date validation aligned to application business clock;
- [x] maintenance/reconciliation has a reusable public guard instead of duplicating closure logic;
- [x] focused regression tests added for DRAFT/CONFIRMED, mid-month period, config lifecycle independence, service error translation, and move source/destination rule.

### Remaining before DONE

- [>] full GitHub Actions pytest suite;
- [ ] audit any regression failures;
- [ ] merge only after green full suite;
- [ ] mark FW2-04 DONE and advance tracker to FW2-05.

## FW2-05 — Settlement Lifecycle

- [ ] confirmation recalculates complete live ledger;
- [ ] expected Cash/Bank closing calculated;
- [ ] actual Cash/Bank required;
- [ ] differences calculated;
- [ ] non-zero difference comment rule enforced;
- [ ] confirmation snapshot atomic;
- [ ] explicit Admin reopen workflow if implemented;
- [ ] remove arbitrary aggregation caps (`limit=100000`);
- [ ] runtime regressions.

## FW2-06 — Wallet Accounting

- [ ] canonical wallets `CASH` / `BANK`;
- [ ] legacy aliases normalized safely;
- [ ] unknown wallet aliases reported, never guessed;
- [ ] opening + income - expense = expected closing;
- [ ] no arbitrary row-limit totals.

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
| 2026-09-24 | Closed-period mutation checks must protect both source and destination when a transaction moves periods. | FINAL |
| 2026-09-24 | PENDING Expense is non-realized and therefore is not blocked solely because its date lies inside a confirmed period. | FINAL |
| 2026-09-24 | All business-date defaults in FW2 posting guards use the application clock. | FINAL |

## Implementation journal

### 2026-09-24 — FW2-04 implementation started

Created branch `finance-wallet-v2-fw2-04` from merged FW2-03 head `main_repos@71f8b73634e1ad19b9399cf9e00b48e19fb5fd4b`. Added central Settlement-derived ledger closure guard, wired Income and realized Expense mutation paths, exposed public FinancePeriod mutability APIs, aligned Expense to application business clock, and added focused closed-period regressions. Full CI pending.

### 2026-09-24 — FW2-03 completed

PR #335 passed the full Windows pytest suite and was merged into main_repos. Audit fixes included migration-chain guard, deterministic application clock usage, and removal of residual post-commit ClassService lookup.

### 2026-09-23 — FW2-02 completed

Expense canonical assignment, future-realized validation, migration `1e10a026`, best-effort post-commit projection, and migration regression fix completed; full rerun later reported green.

### 2026-09-23 — FW2-01 completed

Canonical resolved-period model and transition clamping completed; owner reported runtime regression PASS.
