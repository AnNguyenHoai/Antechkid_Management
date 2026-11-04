# PR J — Legacy Duplicate Enrollment Reconciliation

## Problem

Before PR I, Class Manage Students mapped Remove to WITHDRAWN and a later Enroll always created a new Enrollment row. Because Outstanding is Enrollment-centric, an accidental remove/add could leave two financial contracts for the same student/class and show both balances.

PR I prevents new accidental duplicates. PR J repairs legacy data safely.

## Principle

Reconciliation must not hide or delete financial history.

A duplicate Enrollment remains physically stored. PR J records:

- reconciled_into_enrollment_id
- reconciled_at
- reconciled_by
- reconcile_reason

Operational Enrollment projections exclude reconciled rows, while Student Enrollment history still shows the legacy row and its canonical target.

## Conservative candidate rule

Automatic repair is offered only when:

1. Exactly one current ACTIVE Enrollment exists for the student/class.
2. The suspected duplicate is WITHDRAWN.
3. Neither row is already reconciled.
4. The historical effective session range can be resolved.
5. The ACTIVE canonical contract fully covers the duplicate effective session range.
6. The operator has not already reviewed the row as a legitimate separate contract.

COMPLETED contracts and ambiguous/non-covered histories are not auto-repaired.

## Immutable-ledger blockers

Automatic reconciliation fails closed when the duplicate owns:

- EnrollmentFreeze history
- TuitionAdjustment ledger rows
- EnrollmentTransfer ledger rows

These records are not rewritten heuristically.

## Tuition Income

Tuition Income rows attributed to the duplicate are re-attributed to the canonical Enrollment in the same transaction. Cash amount, payment date, wallet, finance period, status and transaction identity are unchanged.

The audit record contains the moved Income IDs.

## Operator decisions

Class Manage Students exposes **Repair legacy duplicates**.

For each conservative candidate the operator chooses:

- **Reconcile into active** — accidental remove/add; requires a reason.
- **Keep separate** — genuine historical contract; requires a reason and records review metadata so the prompt does not repeat.
- **Cancel**.

## Outstanding behavior

Outstanding remains Enrollment-centric. It does not GROUP BY student/class.

After reconciliation:

- the duplicate Enrollment remains history;
- the duplicate is excluded from operational Outstanding;
- its Tuition Income attribution belongs to the canonical Enrollment;
- Outstanding recalculates from the canonical contract and no longer double-counts the repaired duplicate.

## Migration

Alembic revision: 1e10a040
Down revision: 1e10a039

No historical row is automatically backfilled or guessed during migration.
