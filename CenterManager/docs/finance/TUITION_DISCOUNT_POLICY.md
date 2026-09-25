# TUITION-15 — Enrollment Discount Policy

## Decision

TUITION-15 does **not** introduce a promotion engine. Until promotion eligibility/lifecycle rules are approved, the durable contract is an Enrollment-level discount snapshot.

`Enrollment.discount_amount` remains the canonical effective discount consumed by tuition accrual. New metadata (`discount_type`, `discount_value`, `discount_source`, `discount_reason`, `discount_policy_version`) records how that immutable amount was resolved when the Enrollment contract was created.

Historical Enrollment rows are never recomputed from today's Class fee or a future promotion definition.

## Pricing order

1. Start from the Class course contract (`course_fee`, `planned_sessions`).
2. Resolve the Enrollment session range.
3. Prorate the Class course fee to the Enrollment range → **gross `agreed_course_fee`**.
4. Derive gross `unit_fee = agreed_course_fee / contracted sessions`.
5. Apply an authorized gross agreed-fee override, when explicitly requested.
6. Resolve the Enrollment discount against the final gross agreed fee:
   - `FIXED`: `discount_amount = discount_value`.
   - `PERCENT`: `discount_amount = agreed_course_fee × discount_value / 100`.
7. Persist the resolved discount amount and rule metadata as part of the Enrollment snapshot.
8. Tuition accrual continues to accrue gross tuition from the snapshotted unit fee and releases the snapshotted `discount_amount` proportionally across the contracted sessions.

This keeps discount policy outside Class fee persistence and outside Outstanding arithmetic.

## Manual discount boundary

A new rule-based manual discount must:

- use the existing `TUITION_ENROLLMENT_OVERRIDE` capability;
- identify `discount_source = MANUAL`;
- include a non-empty reason;
- emit `TUITION_ENROLLMENT_DISCOUNT` audit evidence with rule type/value, resolved amount, source, reason, policy version, and gross agreed fee.

The existing raw `discount_amount` input remains supported as a compatibility path for older integrations. It is snapshotted as `FIXED` / `legacy_fixed_v1` but does not fabricate missing historical provenance.

## Historical stability

Accrual reads only the immutable Enrollment `discount_amount`; it does not import or evaluate the discount policy and therefore does not change if future promotion rules change. Existing rows with no discount metadata remain valid and retain their original `discount_amount`.

## Future promotion engine

A future promotion engine may resolve eligibility and pass a rule/source into the same snapshot boundary. It must not make historical Enrollment balances depend on mutable promotion configuration.
