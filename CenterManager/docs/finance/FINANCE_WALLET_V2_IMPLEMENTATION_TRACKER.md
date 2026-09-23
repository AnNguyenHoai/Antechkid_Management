# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** This file supersedes the earlier `FINANCE_WALLET_V2_IMPLEMENTATION_PLAN.md` wherever that file conflicts with `FINANCE_WALLET_V2_DOMAIN_SPEC.md` or `FW2_01_1_PERIOD_MODEL_RECONCILIATION.md`.

## Metadata

| Field | Value |
|---|---|
| Base | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-01 — Canonical FinancePeriod Foundation` |
| Current task | `FW2-01.2 — Canonical resolved-period resolver` |
| Last completed | `FW2-01.1 — Period model reconciliation` |
| Last updated | `2026-09-23` |

Legend: `[ ] TODO` · `[>] CURRENT` · `[~] IN PROGRESS` · `[x] DONE` · `[!] BLOCKED` · `[-] SKIPPED`.

## Domain guardrails

1. Canonical accounting bucket is the **existing FinancePeriod**, resolved to exact inclusive bounds. It is not necessarily a calendar month.
2. Do not create a parallel `FinanceWalletPeriod` calendar-month table.
3. Mid-month anchors and `duration_months > 1` remain valid domain behavior.
4. Canonical resolver must clamp a natural bucket to the owning configuration's effective range so configuration transitions cannot overlap.
5. Every realized Income/Expense must resolve to exactly one covering FinancePeriod before persistence succeeds.
6. Future ACTIVE Income and future COMPLETED Expense are prohibited. Planned money is not realized ledger money.
7. `Settlement.CONFIRMED` closes the resolved FinancePeriod ledger for normal mutation. Do not overload `FinancePeriod.status` with OPEN/FINALIZED.
8. `Class.fee` is the per-student tuition charge for **one canonical FinancePeriod**, not automatically monthly and not multiplied by `duration_months`.
9. Fine-grained Finance capability + WRITE mode + domain-state precondition govern mutation UI; services remain authoritative.
10. Historical data must never be silently reclassified when resolution is ambiguous.

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[>]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[ ]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[ ]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[ ]` | FW2-04 | Closed-period service guard |
| `[ ]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[ ]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[ ]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics |
| `[ ]` | FW2-08 | Canonical period selector + capability/state UI projection |
| `[ ]` | FW2-09 | Backfill/reconciliation/migration exceptions |
| `[ ]` | FW2-10 | Cross-surface regression and production release gate |

## FW2-01 — Canonical FinancePeriod Foundation

### `[x] FW2-01.1` Reconcile persistence/domain model

Decision: reuse existing `FinancePeriod` / `finance_periods`; no new Wallet-period table.

Evidence: `FW2_01_1_PERIOD_MODEL_RECONCILIATION.md`.

Acceptance:

- [x] current SQLAlchemy model mapped;
- [x] Alembic lineage mapped (`1e10a009` foundation);
- [x] repository/service architecture mapped;
- [x] no destructive conflict with historical FinancePeriod;
- [x] schema compatibility path documented;
- [x] initial tracker errors identified and corrected.

Implementation note: FW2-01.1 is a design/persistence reconciliation gate; intentionally no production schema/code mutation is required.

### `[>] FW2-01.2` Implement canonical resolved-period resolver

Target result:

```text
target date
  → effective FinancePeriod configuration
  → natural bucket from effective_from + duration_months
  → clamp to owning configuration effective_from/effective_to
  → exact canonical period_start/period_end
```

Required coverage:

- [ ] normal bucket;
- [ ] mid-month bucket;
- [ ] duration > 1 month;
- [ ] leap-year behavior;
- [ ] configuration transition truncates previous bucket;
- [ ] no overlap across transition;
- [ ] historical INACTIVE configuration remains resolvable by date;
- [ ] date with no configuration resolves none/validation failure according to caller contract.

### `[ ] FW2-01.3` Runtime regression tests

Tests must execute model/repository/service behavior; source-token assertions are insufficient.

### `[ ] FW2-01.4` Phase review

- [ ] all Finance period consumers can receive exact selected bounds;
- [ ] Month/Year inference is no longer required as canonical identity;
- [ ] F-20 overlap case is closed;
- [ ] all FW2-01 tests green.

## FW2-02 — Expense Period Assignment

- [ ] add canonical period assignment bridge/FK according to approved migration shape;
- [ ] require unique covering FinancePeriod for COMPLETED Expense;
- [ ] reject future COMPLETED Expense;
- [ ] allow future PENDING only as non-realized;
- [ ] recompute assignment when date changes;
- [ ] legacy deterministic backfill support;
- [ ] ambiguous rows become migration exceptions;
- [ ] fix post-commit false-failure boundary;
- [ ] runtime regressions.

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
- [ ] service remains authoritative;
- [ ] legacy Finance UI production debt handled without changing accounting rules.

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
| 2026-09-23 | Resolved bucket must be clamped to configuration effective bounds. | FINAL |
| 2026-09-23 | Settlement confirmation owns ledger closure; `FinancePeriod.status` remains configuration lifecycle. | FINAL |
| 2026-09-23 | `Class.fee` is per canonical FinancePeriod, not per calendar month. | FINAL |
| 2026-09-23 | Future realized postings are rejected, not treated as planned actuals. | FINAL |

## Implementation journal

### 2026-09-23 — FW2-01.1 completed

Reviewed the approved Domain Spec against the actual `FinancePeriod` model, repository, service and Alembic foundation. The first tracker incorrectly proposed a separate calendar-month Wallet period. FW2-01.1 corrects that direction: reuse the existing effective-dated FinancePeriod architecture and make the resolved exact bucket canonical. No production schema change is required for this reconciliation task.

**Next:** FW2-01.2 — implement effective-range-clamped canonical resolver and close audit F-20.
