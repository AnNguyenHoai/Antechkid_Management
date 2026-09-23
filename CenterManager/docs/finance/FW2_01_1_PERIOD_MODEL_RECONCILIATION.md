# FW2-01.1 — FinancePeriod Model Reconciliation

Status: **DONE**  
Base: `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8`  
Domain source: `FINANCE_WALLET_V2_DOMAIN_SPEC.md`  
Date: 2026-09-23

## 1. Decision

Wallet V2 **MUST reuse the existing `FinancePeriod` domain and `finance_periods` table**. It must **not** introduce a parallel `FinanceWalletPeriod` calendar-month entity.

The approved Domain Spec defines FinancePeriod as the canonical accounting bucket with exact inclusive bounds and explicitly allows periods such as `15/09/2026 – 14/10/2026`. `duration_months` may be greater than one. Therefore a calendar-month-only Wallet period would conflict with the approved contract.

Canonical identity for Finance operations is the resolved period instance plus its exact bounds, with `period_start` used as the current compatibility identity where a real FK has not yet been migrated.

## 2. Current persistence mapped

Existing SQLAlchemy model:

```text
FinancePeriod / finance_periods
- id                PK
- duration_months   1..24
- status            ACTIVE / INACTIVE
- effective_from
- effective_to      nullable
- created_at
- updated_at

UNIQUE(effective_from)
CHECK(effective_to IS NULL OR effective_to >= effective_from)
```

Existing Alembic lineage created the table in revision `1e10a009`. Current repository/provider architecture already exposes `FinancePeriodRepository`; `FinancePeriodService` already resolves the effective configuration for a date.

No new period table is required for FW2-01.

## 3. Important semantic distinction

The current row is an **effective-dated period configuration**, while Finance consumers also need the **resolved canonical accounting bucket** generated from that configuration.

Example:

```text
configuration:
  effective_from = 2026-08-15
  duration_months = 1

resolved bucket containing 2026-09-20:
  2026-09-15 .. 2026-10-14
```

A later configuration may truncate the owning configuration's effective range. The resolved bucket therefore must be clamped to the owning configuration's `effective_from/effective_to` range so two configurations cannot claim the same transaction date.

This directly addresses audit finding F-20.

## 4. Target V2 period contract

FW2-01.2 should introduce one canonical resolver API around the existing entity, conceptually:

```python
@dataclass(frozen=True)
class ResolvedFinancePeriod:
    configuration_id: int
    period_start: date
    period_end: date
    duration_months: int

    def contains(self, value: date) -> bool: ...
```

Suggested service API:

```python
resolve_period(target_date: date) -> Optional[ResolvedFinancePeriod]
resolve_period_by_start(period_start: date) -> Optional[ResolvedFinancePeriod]
list_resolved_periods(...) -> list[ResolvedFinancePeriod]
```

Resolution algorithm:

```text
1. find FinancePeriod configuration effective on target_date;
2. calculate natural bucket from configuration.effective_from + duration_months;
3. clamp bucket start/end to configuration effective bounds;
4. verify target_date remains inside the clamped bucket;
5. return exact canonical bounds and owning configuration id.
```

Consumers must not infer a FinancePeriod from Month/Year.

## 5. Persistence strategy for transaction assignment

Wallet V2 target contract requires realized Income and Expense to belong to exactly one FinancePeriod.

Current compatibility state:

- Income already persists `finance_period_start` as a period classification bridge.
- Expense does not yet have equivalent canonical period assignment.

Migration direction:

1. keep `finance_period_start` readable during incremental migration;
2. add real FinancePeriod ownership/classification for Income/Expense in later tasks where safe;
3. transaction date + canonical resolver must agree with persisted assignment;
4. if a transaction date has no unique covering FinancePeriod, realized persistence must fail;
5. legacy Expense backfill may assign only when resolution is deterministic;
6. ambiguous/unresolvable legacy rows become migration exceptions, never arbitrary assignments.

A real FK must refer to the existing FinancePeriod configuration/entity architecture rather than a new calendar-month table. If a future schema needs an explicit persisted resolved-bucket entity, that requires a separate approved domain migration because the current Domain Spec does not authorize replacing FinancePeriod with calendar months.

## 6. Settlement closure ownership

Do not add `OPEN/FINALIZED` to `FinancePeriod.status` in FW2-01. Existing status means configuration lifecycle (`ACTIVE/INACTIVE`), not ledger closure.

Wallet V2 ledger closure is derived from Settlement state:

```text
Settlement.CONFIRMED
    <=> selected resolved FinancePeriod is closed for normal realized mutation
```

This avoids overloading `FinancePeriod.status` with two unrelated state machines.

FW2-04/FW2-05 will implement the closed-period guard and atomic confirmation semantics.

## 7. Compatibility rules

The following are fixed for implementation:

- keep `finance_periods` and existing historical rows;
- keep `duration_months` semantics;
- keep mid-month anchors;
- keep historical effective ranges;
- do not normalize periods to calendar months;
- do not create `FinanceWalletPeriod`;
- do not reinterpret `Class.fee` as monthly: Domain Spec defines it as the per-student charge for **one canonical FinancePeriod**, regardless of period duration;
- do not allow future ACTIVE Income or future COMPLETED Expense in V2; future realized postings must fail validation rather than merely be hidden from Actual totals.

## 8. Schema compatibility path

### FW2-01

No schema migration. Reconcile semantics and implement canonical resolution on existing `FinancePeriod`.

### FW2-02 / FW2-03

Migrate transaction period assignment incrementally. Preserve compatibility columns/read paths until backfill and regression gates prove safe.

### FW2-04 / FW2-05

Use Settlement confirmation as ledger-closure source of truth; do not mutate `FinancePeriod.status` semantics.

### FW2-09

Backfill legacy transaction assignment only through the canonical resolver. Report ambiguous/unresolved rows.

## 9. Acceptance criteria result

- [x] Persistence approach mapped to current SQLAlchemy/Alembic/repository architecture.
- [x] No destructive conflict with existing FinancePeriod.
- [x] Naming/domain ownership reconciled: existing `FinancePeriod` remains canonical; no parallel Wallet period entity.
- [x] Schema compatibility path documented.
- [x] Domain Spec checked against current implementation before schema work.

## 10. Corrections to the initial implementation tracker

The initial tracker was written from an incorrect reading of the Domain Spec and must be corrected before subsequent implementation:

1. `canonical calendar month` → `canonical resolved FinancePeriod with exact bounds`;
2. remove proposed `FinanceWalletPeriod` table;
3. `Class.fee = monthly tuition` → `Class.fee = charge per student per canonical FinancePeriod`;
4. future ACTIVE Income is not a supported planned state; V2 prohibits future realized posting;
5. Expense membership is not merely date-authoritative with a stale FK tolerated forever: V2 requires persisted assignment to agree with the canonical period before realized persistence succeeds;
6. Settlement domain uses `CONFIRMED`, not a new `FinancePeriod.FINALIZED` lifecycle.

These corrections are mandatory for FW2-01.2 onward.

## 11. Next task

`FW2-01.2 — Implement canonical resolved FinancePeriod resolver with effective-range clamping.`

The first regression target is the transition case from audit F-20:

```text
old config: effective_from 15/08/2026, duration 1 month
new config: effective_from 01/09/2026

old natural bucket: 15/08–14/09
old canonical clamped bucket: 15/08–31/08
new canonical bucket: 01/09–30/09

No overlap.
```
