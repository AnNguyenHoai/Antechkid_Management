# Finance Wallet V2 — Implementation Plan & Progress Tracker

> **Purpose:** Living implementation tracker for Finance Wallet V2.  
> This file is the operational source of truth for implementation progress, current work, decisions, notes, regressions, and hand-off between phases.

## 0. Tracker metadata

| Field | Value |
|---|---|
| Base snapshot | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Domain source of truth | `docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Supporting evidence | `FINANCE_WORKSPACE_AUDIT_2026-09-23.md`, `FINANCE_WORKSPACE_AUDIT_PASS3_2026-09-23.md` |
| Plan status | `ACTIVE` |
| Current phase | `FW2-01 — Canonical Wallet Period Foundation` |
| Current task | `FW2-01.1 — Reconcile canonical Wallet Period model with legacy FinancePeriod` |
| Last updated | `2026-09-23` |

### Status legend

- `[ ] TODO` — not started.
- `[>] CURRENT` — current implementation focus. There should normally be only one current task.
- `[~] IN PROGRESS` — started but not the immediate focus.
- `[x] DONE` — implemented and verified against its acceptance criteria.
- `[!] BLOCKED` — cannot proceed until the recorded blocker/decision is resolved.
- `[-] SKIPPED` — intentionally not implemented; reason must be recorded.

### Update rule

After every implementation task or PR:

1. update **Current phase / Current task** above;
2. update the checkbox/status in the master roadmap;
3. add implementation notes under that task;
4. record commit/PR/test evidence;
5. record any domain decision or deviation;
6. move `[>] CURRENT` to the next task only after the previous task's acceptance criteria are satisfied.

Do not mark a task `DONE` only because code was written. `DONE` means implementation + regression verification + relevant documentation/migration checks are complete.

---

# 1. Fixed domain decisions

These decisions come from `FINANCE_WALLET_V2_DOMAIN_SPEC.md` and must not be changed implicitly during implementation.

1. Wallet V2 operating period is a **canonical calendar month**.
2. Legacy/custom `FinancePeriod` data must remain backward-compatible; do not destructively reinterpret historical periods.
3. Expense period membership is determined by `expense_date`; a persisted period FK is classification/optimization, not the ultimate source of truth.
4. Future-dated Income is not realized Actual Income.
5. Voided Income is never realized Actual Income.
6. `saving = realized income - realized expense`; negative values remain negative.
7. A FINALIZED period closes the underlying financial ledger, not only the Settlement snapshot.
8. Reopening a finalized period must be an explicit authorized action.
9. `Class.fee` means expected **monthly tuition obligation per eligible student** for Wallet projection semantics.
10. Projection must expose reliability/unknown state instead of inventing missing fixed-expense data.
11. Financial totals must not depend on arbitrary row limits.
12. UI must consume domain/service results rather than independently implementing accounting rules.

## Known specification/repository mismatch

At the base snapshot, `FINANCE_WALLET_V2_DOMAIN_SPEC.md` references `FINANCE_WALLET_V2_EXECUTION_CONTRACT.md` and `FINANCE_PERIOD_CAPABILITY_CONTRACT.md`, but those files are not present under `docs/finance`. Until they exist and are reconciled, the Domain Spec plus verified repository behavior/audit findings are the implementation source of truth.

---

# 2. Master roadmap

| Status | ID | Phase | Primary outcome | Depends on |
|---|---|---|---|---|
| `[>]` | FW2-01 | Canonical Wallet Period Foundation | One canonical calendar-month identity and resolver | — |
| `[ ]` | FW2-02 | Expense Period Assignment | Expense consistently belongs to canonical month | FW2-01 |
| `[ ]` | FW2-03 | Income Realized Semantics | Future/voided Income excluded from actual money | FW2-01 |
| `[ ]` | FW2-04 | Closed-period Guard | One service-level mutation lock boundary | FW2-01..03 |
| `[ ]` | FW2-05 | Settlement Lifecycle | Finalize/reopen correctly closes/opens ledger | FW2-04 |
| `[ ]` | FW2-06 | Wallet Aggregate & DTO | One authoritative actual/saving read model | FW2-02..05 |
| `[ ]` | FW2-07 | Projection Engine | Reliable next-month projection semantics | FW2-06 |
| `[ ]` | FW2-08 | Wallet UI Integration | UI consumes canonical Wallet domain | FW2-06..07 |
| `[ ]` | FW2-09 | Backfill & Reconciliation | Existing data upgraded safely/idempotently | FW2-01..08 |
| `[ ]` | FW2-10 | Capability & Regression Gate | Production hardening and release gate | FW2-01..09 |

Recommended dependency flow:

```text
FW2-01
  ├── FW2-02 Expense
  └── FW2-03 Income
          │
          ▼
      FW2-04 Closed-period Guard
          │
          ▼
      FW2-05 Settlement
          │
          ▼
      FW2-06 Aggregate/DTO
          │
          ▼
      FW2-07 Projection
          │
          ▼
      FW2-08 UI
          │
          ▼
      FW2-09 Backfill
          │
          ▼
      FW2-10 Release Gate
```

---

# 3. FW2-01 — Canonical Wallet Period Foundation

**Phase status:** `[>] CURRENT`

## Goal

Introduce exactly one Wallet V2 calendar-month identity/resolver without destructively changing legacy/custom `FinancePeriod` semantics.

## Tasks

### `[>] FW2-01.1` Reconcile canonical Wallet Period model with legacy FinancePeriod

Confirm the final persistence design before schema changes.

Target design:

```text
FinanceWalletPeriod
- id
- period_name       e.g. 2026-09
- period_start      e.g. 2026-09-01
- period_end        e.g. 2026-09-30
- status            OPEN / FINALIZED
- created_at
- updated_at

UNIQUE(period_start)
```

Rules:

- do not convert existing custom `FinancePeriod` records into calendar months;
- do not delete/rename legacy period structures solely for Wallet V2;
- preserve a migration path for future multi-center uniqueness `(center_id, period_start)` if center ownership is later added consistently to finance entities.

**Acceptance criteria**

- [ ] persistence approach is mapped to current SQLAlchemy/bootstrap/migration architecture;
- [ ] no destructive conflict with legacy `FinancePeriod`;
- [ ] naming avoids confusing configuration periods with Wallet operating periods;
- [ ] schema compatibility path is documented.

**Implementation notes:** _pending_

**Evidence / commit / PR:** _pending_

### `[ ] FW2-01.2` Implement canonical calendar-month resolver

Required service operations:

```python
get_month_range(reference_date)
get_or_create_wallet_period(reference_date)
get_wallet_period(reference_date)
get_wallet_period_by_id(period_id)
is_period_finalized(period_id)
ensure_period_is_mutable(period_id_or_date)
```

No Dashboard/ViewModel/UI may duplicate month-boundary logic.

**Acceptance criteria**

- [ ] February normal year;
- [ ] February leap year;
- [ ] 30-day month;
- [ ] 31-day month;
- [ ] December → January boundary;
- [ ] get-or-create is idempotent;
- [ ] legacy FinancePeriod behavior remains intact.

### `[ ] FW2-01.3` Add repository/model regression tests

Tests must execute runtime behavior, not source-token assertions.

### `[ ] FW2-01.4` Review phase boundary

Before FW2-02/03 begin:

- [ ] canonical period identity is stable;
- [ ] no overlapping Wallet periods can exist;
- [ ] no consumer needs to infer Wallet period from legacy duration-based configuration;
- [ ] all FW2-01 tests pass.

---

# 4. FW2-02 — Expense Period Assignment

**Phase status:** `[ ] TODO`

## Goal

Every Expense is consistently classified into its canonical Wallet month while `expense_date` remains authoritative.

## Tasks

### `[ ] FW2-02.1` Add Wallet-period classification to Expense persistence

Add an appropriate Wallet-period FK/reference while preserving legacy rows.

### `[ ] FW2-02.2` Assign period on Expense create

```text
expense_date
  → canonical month resolver
  → get/create Wallet Period
  → persist classification
```

### `[ ] FW2-02.3` Reassign period when Expense date crosses month

Same-month edits retain period. Cross-month edits reassign it.

### `[ ] FW2-02.4` Make date membership authoritative in reads

A NULL/stale classification must not make a correctly dated Expense disappear from the period aggregate.

### `[ ] FW2-02.5` Fix post-commit false-failure boundary for Expense

Primary committed financial state determines mutation success. Timeline/event projection must not turn a successful money commit into a user-visible save failure.

### `[ ] FW2-02.6` Expense regression suite

Required coverage:

- [ ] first day included;
- [ ] last day included;
- [ ] next month excluded;
- [ ] NULL FK compatibility;
- [ ] stale FK compatibility;
- [ ] date move across month;
- [ ] delete refreshes totals;
- [ ] timeline failure cannot cause duplicate-retry semantics.

---

# 5. FW2-03 — Income Realized Semantics

**Phase status:** `[ ] TODO`

## Goal

Define one authoritative rule for realized Income and use it consistently across Wallet, Dashboard, Outstanding, and Settlement.

## Tasks

### `[ ] FW2-03.1` Introduce authoritative realized-Income predicate/query

Current-schema mapping:

```text
ACTIVE + payment_date <= today  => realized
ACTIVE + payment_date > today   => future/planned, not actual
VOIDED                           => never realized
```

Do not rename the existing lifecycle merely to mimic Domain Spec terminology.

### `[ ] FW2-03.2` Replace divergent Income calculations

Remove independent future-date semantics from Dashboard/Settlement/Outstanding where applicable.

### `[ ] FW2-03.3` Add date-aware enrollment validation

Validate student-linked Income against enrollment coverage at `payment_date`, not only current ACTIVE enrollment status.

### `[ ] FW2-03.4` Fix post-commit false-failure boundary for Income

Same success rule as Expense.

### `[ ] FW2-03.5` Income regression suite

- [ ] ACTIVE past = actual;
- [ ] ACTIVE today = actual;
- [ ] ACTIVE future = not actual;
- [ ] VOIDED = not actual;
- [ ] date change across month recalculates membership;
- [ ] historical enrollment validity is transaction-date aware;
- [ ] timeline failure cannot cause duplicate-retry semantics.

---

# 6. FW2-04 — Closed-period Guard

**Phase status:** `[ ] TODO`

## Goal

Create one domain/service guard that prevents ledger mutation after a period is FINALIZED.

## Tasks

### `[ ] FW2-04.1` Implement central mutability guard

Suggested boundary:

```python
FinancePeriodService.ensure_period_is_mutable(...)
```

### `[ ] FW2-04.2` Apply guard to Expense mutations

Create/update/delete and any state transition that changes realized money.

### `[ ] FW2-04.3` Apply guard to Income mutations

Create/update/void/delete and any state transition that changes realized money.

### `[ ] FW2-04.4` Apply guard to reconciliation/backfill mutation paths

No maintenance path may silently bypass finalized-period integrity.

### `[ ] FW2-04.5` Closed-period regression suite

Service enforcement is authoritative; disabled UI controls are not sufficient evidence.

---

# 7. FW2-05 — Settlement Lifecycle

**Phase status:** `[ ] TODO`

## Goal

Make Settlement FINALIZED mean the period's underlying ledger is closed.

## Tasks

### `[ ] FW2-05.1` Atomic finalize transaction

Required logical transaction:

```text
BEGIN
resolve canonical Wallet Period
verify mutable
calculate realized Income
calculate realized Expense
calculate saving
persist final snapshot
mark FINALIZED
COMMIT
```

No half-finalized state.

### `[ ] FW2-05.2` Explicit authorized reopen command

```text
FINALIZED → OPEN/DRAFT
```

Reopen must be audited and capability protected.

### `[ ] FW2-05.3` Remove silent Settlement aggregation caps

Financial totals must use database aggregation or count-driven complete reads, never arbitrary row limits.

### `[ ] FW2-05.4` Settlement regression suite

- [ ] finalize recomputes actual;
- [ ] snapshot saved;
- [ ] finalization atomic;
- [ ] Income/Expense mutations blocked afterward;
- [ ] read remains allowed;
- [ ] authorized reopen works;
- [ ] mutation works after reopen;
- [ ] failure rolls back the whole finalize operation.

---

# 8. FW2-06 — Wallet Aggregate & DTO

**Phase status:** `[ ] TODO`

## Goal

Provide one authoritative read model for Wallet actuals.

## Target DTO

```python
FinanceWalletPeriodSummary(
    period_id,
    period_start,
    period_end,
    status,
    total_income,
    total_expense,
    saving_amount,
    is_locked,
)
```

## Tasks

### `[ ] FW2-06.1` Implement aggregate service/repository query

No arbitrary 10k/100k row cap.

### `[ ] FW2-06.2` Define signed saving

```text
saving_amount = total_income - total_expense
```

Never clamp negative values to zero.

### `[ ] FW2-06.3` Align Dashboard/Settlement read semantics

All surfaces must consume the same realized-money rules.

### `[ ] FW2-06.4` Aggregate regression suite

Include high-volume behavior proving totals do not truncate.

---

# 9. FW2-07 — Projection Engine

**Phase status:** `[ ] TODO`

## Goal

Produce explainable next-month projection without contaminating historical actuals.

## Target DTO

```python
FinanceProjectionResult(
    reference_month,
    next_month,
    expected_income,
    expected_fixed_expense,
    projected_available_balance,
    income_projection_reliable,
    expense_projection_reliable,
    projection_notes,
)
```

## Tasks

### `[ ] FW2-07.1` Implement expected tuition projection

`Class.fee` means expected monthly tuition obligation per eligible student.

### `[ ] FW2-07.2` Define precedence/deduplication

Scheduled Income and class-fee projection must not double count the same obligation.

### `[ ] FW2-07.3` Protect historical correctness

Changing current `Class.fee` must not rewrite finalized historical actuals/snapshots.

### `[ ] FW2-07.4` Implement fixed-expense reliability contract

If no trustworthy recurring/fixed-expense domain source exists:

```text
expected_fixed_expense = 0
expense_projection_reliable = False
```

with an explanatory note. Do not fabricate a forecast from unrelated historical averages.

### `[ ] FW2-07.5` Projection regression suite

- [ ] eligible enrollment included;
- [ ] ineligible enrollment excluded;
- [ ] next-month date eligibility;
- [ ] no double counting;
- [ ] negative available balance preserved;
- [ ] missing expense source reports unreliable projection.

---

# 10. FW2-08 — Wallet UI Integration

**Phase status:** `[ ] TODO`

## Goal

Make Finance UI a projection of the Wallet domain rather than a second accounting engine.

## Tasks

### `[ ] FW2-08.1` Replace ambiguous month/year inference

Use canonical Wallet Period identity/bounds.

### `[ ] FW2-08.2` Bind Wallet summary cards to aggregate DTO

Preferred copy:

- `Thu nhập đã ghi nhận`
- `Chi phí đã ghi nhận`
- `Tiết kiệm / Thâm hụt`

### `[ ] FW2-08.3` Bind projection cards

- `Thu nhập dự kiến tháng sau`
- `Chi phí cố định dự kiến tháng sau`
- `Số dư khả dụng dự kiến`

Projection reliability must be visible when data is incomplete.

### `[ ] FW2-08.4` Project FINALIZED state into actions

Income/Expense mutation controls disabled when locked, while service guards remain authoritative.

### `[ ] FW2-08.5` Project fine-grained capabilities

UI actions should reflect `finance.income.*`, `finance.expense.*`, settlement/reopen capabilities instead of only broad WRITE mode.

### `[ ] FW2-08.6` UI/runtime regression suite

No source-token-only tests for critical behavior.

---

# 11. FW2-09 — Backfill & Reconciliation

**Phase status:** `[ ] TODO`

## Goal

Upgrade existing data safely without silently rewriting historical accounting meaning.

## Tasks

### `[ ] FW2-09.1` Expense period backfill

For each Expense:

```text
expense_date
→ canonical calendar month
→ get/create Wallet Period
→ assign classification
```

### `[ ] FW2-09.2` Make backfill idempotent

Second run should produce zero semantic changes when data has not changed.

### `[ ] FW2-09.3` Produce reconciliation metrics

At minimum:

```text
inspected
assigned
reassigned
unchanged
failed
```

### `[ ] FW2-09.4` Preserve Income future records

Do not delete or rewrite valid future ACTIVE Income merely because it is not realized yet.

### `[ ] FW2-09.5` Preserve legacy periods and historical Settlement snapshots

No destructive conversion of custom historical ranges.

### `[ ] FW2-09.6` Backfill regression suite

Test first run, second run, stale classification repair, legacy records, and finalized-period protection.

---

# 12. FW2-10 — Capability & Regression Gate

**Phase status:** `[ ] TODO`

## Goal

Make Wallet V2 production-ready and establish the release gate.

## Tasks

### `[ ] FW2-10.1` Capability matrix verification

Verify read/create/update/void/delete/finalize/reopen paths at service and UI levels.

### `[ ] FW2-10.2` End-to-end Finance consistency tests

Dashboard, Income, Expense, Wallet summary, Outstanding, and Settlement must agree on shared semantics.

### `[ ] FW2-10.3` High-volume aggregate tests

Prove no silent truncation from UI/service row caps.

### `[ ] FW2-10.4` Historical compatibility tests

Legacy Expense values, legacy FinancePeriod records, archived entities, and historical Settlement snapshots remain readable.

### `[ ] FW2-10.5` Final production audit

Re-run the Finance audit against the implementation and record any residual findings below.

### `[ ] FW2-10.6` Release checklist

Wallet V2 is complete only when every Definition of Done item is satisfied.

---

# 13. Definition of Done — Wallet V2

- [ ] Calendar month is the canonical Wallet operating period.
- [ ] No UI duplicates canonical month-boundary calculations.
- [ ] Expense auto-assigns/reassigns Wallet period.
- [ ] Expense date remains authoritative for membership.
- [ ] Future Income is excluded from Actual.
- [ ] VOIDED Income is excluded from Actual.
- [ ] Total Income/Expense have one authoritative aggregate source.
- [ ] Saving remains signed: `income - expense`.
- [ ] FINALIZED locks Income/Expense mutation at service level.
- [ ] Reopen exists and is authorized/audited.
- [ ] `Class.fee` has one Wallet meaning: expected monthly tuition.
- [ ] Projection avoids double counting.
- [ ] Projection reports reliability instead of fabricating missing data.
- [ ] Historical custom FinancePeriod records remain intact.
- [ ] Finalized historical snapshots are not silently rewritten.
- [ ] Financial totals have no arbitrary row-limit truncation.
- [ ] Migration/backfill is idempotent.
- [ ] Dashboard/List/Settlement use consistent realized-money semantics.
- [ ] Runtime regression tests cover month boundaries, future postings, lock/reopen, stale classification, and high-volume totals.
- [ ] UI contains no independent accounting formula that conflicts with domain services.

---

# 14. Decision log

Use this section whenever implementation uncovers a decision that affects later phases.

| Date | Decision | Reason | Affected tasks | Status |
|---|---|---|---|---|
| 2026-09-23 | Treat `FINANCE_WALLET_V2_DOMAIN_SPEC.md` as the Wallet V2 domain source of truth until missing referenced contracts are available/reconciled. | Referenced execution/capability contract files are absent from the base snapshot. | All | ACTIVE |
| 2026-09-23 | Do not destructively repurpose legacy/custom `FinancePeriod` into Wallet calendar months. | Existing behavior/audits rely on effective-dated custom periods; Wallet needs an unambiguous calendar-month identity. | FW2-01, FW2-09 | ACTIVE |

---

# 15. Implementation journal

Add newest entries at the top. Keep entries concise but sufficient for the next implementation session to resume without reconstructing context.

## 2026-09-23 — Plan initialized

**Base:** `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8`

**Current:** `FW2-01.1 — Reconcile canonical Wallet Period model with legacy FinancePeriod`

**Notes:**

- Wallet V2 implementation is intentionally domain-first; do not begin with Dashboard visual changes.
- Existing audits already identify period overlap, future-posting inconsistency, Settlement closure ambiguity, aggregation caps, mutable historical fee semantics, and transaction-date enrollment validation as Finance integrity risks.
- FW2-01 must establish a stable canonical month identity before Expense/Income changes proceed.

**Next action:** inspect current persistence/bootstrap/migration patterns and implement the canonical Wallet Period foundation without changing legacy FinancePeriod semantics.

---

# 16. Residual issues / blockers

Record unresolved issues here instead of hiding them inside implementation code.

| ID | Issue | Impact | Owner/decision needed | Status |
|---|---|---|---|---|
| B-01 | Domain Spec references `FINANCE_WALLET_V2_EXECUTION_CONTRACT.md` and `FINANCE_PERIOD_CAPABILITY_CONTRACT.md`, absent at base snapshot. | Capability/execution details must be reconstructed from verified code/audits until reconciled. | Finance Wallet V2 implementation | OPEN |
| B-02 | Current Income lifecycle naming differs from Domain Spec terminology. | Must map semantics rather than perform risky cosmetic lifecycle migration. | FW2-03 | RESOLVED BY PLAN |
| B-03 | Finance entities do not yet expose a consistent `center_id` ownership model. | Do not prematurely build multi-center Wallet uniqueness around inconsistent schema. | Future domain evolution | DEFERRED |

---

# 17. Session resume checklist

When starting a new Wallet V2 implementation session, read in this order:

1. `FINANCE_WALLET_V2_DOMAIN_SPEC.md`;
2. this `FINANCE_WALLET_V2_IMPLEMENTATION_PLAN.md`;
3. **Tracker metadata** for Current phase/task;
4. the current task's Implementation notes/Evidence;
5. Decision log;
6. Residual issues/blockers;
7. only then inspect the relevant code and continue implementation.

This tracker must be updated before closing each completed phase/task so the next session can resume from repository state rather than conversation memory.
