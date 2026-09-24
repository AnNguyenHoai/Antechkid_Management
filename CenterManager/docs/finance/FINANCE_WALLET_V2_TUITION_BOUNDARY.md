# Finance Wallet V2 — Accounting / Tuition Boundary

Status: **APPROVED DOMAIN AMENDMENT**  
Date: 2026-09-24  
Issue: #342 — FW2-09

## Purpose

This amendment records the product decision discovered after FW2-08 audit: `FinancePeriod` is an **Accounting / Settlement Period** only. It is not a course duration, tuition period, enrollment billing cycle, or source of tuition obligation.

This amendment supersedes the tuition-specific semantics in `FINANCE_WALLET_V2_DOMAIN_SPEC.md` sections 3.4, R5, 7, Migration Phase D, Acceptance Criterion 5, and the regression case that treats `Class.fee` as a per-FinancePeriod charge. Accounting, Wallet and Settlement rules in that specification remain authoritative.

## Canonical boundary

### FinancePeriod owns accounting time

`FinancePeriod` is used for:

- canonical Income posting;
- canonical realized Expense posting;
- `CASH` / `BANK` ledger aggregation;
- Dashboard accounting projections;
- Settlement reconciliation;
- ledger close/reopen state;
- accounting export/report bounds.

A realized financial posting still belongs to exactly one canonical FinancePeriod.

### Tuition owns academic obligation

Tuition obligation is derived from the academic contract:

```text
Class course contract
        ↓
Enrollment tuition snapshot
        ↓
Billable Sessions
        ↓
Tuition Accrual
        ↓
Outstanding / Prepaid balance
```

`FinancePeriod.duration_months`, `period_start`, and `period_end` MUST NOT determine:

- course duration;
- total course tuition;
- per-session tuition;
- enrollment agreed tuition;
- whether an academic session is billable;
- the amount of tuition accrued by an enrollment.

## Target tuition formula

The target domain is enrollment-centric:

```text
unit_fee = agreed_course_fee / planned_sessions

tuition_accrued = billable_sessions × unit_fee

balance = tuition_accrued - tuition_paid
```

The exact pricing/snapshot rules are implemented incrementally by TUITION-01 through TUITION-10. Attendance-aware billing is a later policy extension.

## Payment / accounting bridge

A Tuition payment remains a realized `Income` transaction. Therefore its payment date resolves to an Accounting `FinancePeriod` and its wallet is `CASH` or `BANK`.

Separately, the payment is attributed to an Enrollment for tuition balance calculation.

```text
Enrollment ← Tuition payment attribution → Income → FinancePeriod / Wallet
```

Changing the accounting period never creates, removes, or reprices the academic tuition obligation.

## Transitional Outstanding exception

`OutstandingService` currently contains the FW2-07 implementation that derives expected tuition from historical `Class.fee` inside a selected FinancePeriod. That behavior is **transitional compatibility**, not the target tuition contract.

Until TUITION-08 (#350) replaces it:

- do not extend the period-based obligation formula;
- do not add new tuition features that depend on FinancePeriod identity;
- preserve current behavior only for regression safety;
- route new tuition-domain work through Class / Enrollment / Session contracts.

The transitional exception ends when Outstanding V2 is merged.

## Architecture guard

New academic/tuition core modules must not import `FinancePeriod`, `FinancePeriodService`, or `models.finance_period` to calculate tuition obligation.

Permitted dependencies are accounting-side modules whose responsibility is transaction posting, reporting, Wallet aggregation or Settlement. The known transitional `OutstandingService` dependency is temporary and must remain explicitly documented until #350.

## Roadmap

- #343 TUITION-01 — Class Course & Tuition Contract
- #344 TUITION-02 — Class Create/Edit Tuition UX
- #345 TUITION-03 — Enrollment Tuition Snapshot Contract
- #346 TUITION-04 — Mid-course Enrollment Pricing & Session Range
- #347 TUITION-05 — Billable Session Policy
- #348 TUITION-06 — Tuition Accrual Service
- #349 TUITION-07 — Link Tuition Payments to Enrollment
- #350 TUITION-08 — Outstanding V2 Core
- #351 TUITION-09 — Prepaid / Credit Balance Semantics
- #352 TUITION-10 — Student Tuition Detail UX

## Invariants

```text
FinancePeriod == accounting / settlement boundary
```

```text
FinancePeriod != course / tuition obligation boundary
```

```text
Academic obligation is created by Class + Enrollment + billable Session semantics
```

No future implementation may restore the superseded `Class.fee per FinancePeriod` contract without a new explicit product/domain decision.