# FINANCE-1.1 — Data Integrity & Outstanding Contract

## Contract

The tuition balance unit is the enrolled `(student_id, class_id)` pair.

`Enrollment -> Class.fee -> Expected Tuition`
`Tuition Income(student_id, class_id) -> Paid`

Only `Income.income_type == "Tuition"` settles tuition. Book, Robot Kit,
Material and Other income must never reduce tuition outstanding.

## Missing tuition configuration

An enrollment whose class has `fee is None` or `fee <= 0` is returned with:

- `status = No Tuition Configured`
- `tuition_configured = False`
- expected tuition = 0
- outstanding = 0

This means **unknown/not configured**, not **paid**.

Student summaries expose `has_unconfigured_tuition`. Unconfigured classes are
not included in aggregate expected/paid/outstanding debt arithmetic.

## Multi-class rule

Each enrollment is calculated independently. A payment for one class cannot
settle another class because both `student_id` and `class_id` are required by
the income contract and the outstanding query filters both keys.

## Scope

This task does not introduce a new TuitionObligation table or migrate Income
into a separate payment aggregate. Those are deferred until Finance requires
more complex obligations, discounts, refunds or cross-class payment allocation.
