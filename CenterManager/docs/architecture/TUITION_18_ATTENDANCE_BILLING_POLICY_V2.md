# TUITION-18 — Attendance Billing Policy V2

## Purpose

TUITION-18 aligns the canonical tuition rule with the approved business meaning that a delivered/reserved teaching session remains billable when a student is `Absent` or `Excused`.

The change is versioned. It does **not** mutate `attendance_v1`, because each Enrollment snapshots its billing-policy version and historical tuition must remain auditable.

## Evaluation order

1. The Session must be `Completed`.
2. The Session must belong to the Enrollment class and be inside the inclusive Enrollment session range.
3. Enrollment freeze rules are applied.
4. The Enrollment's `billing_policy_version` selects the attendance rule.
5. The selected attendance rule decides billability.

Attendance never makes `Scheduled`, `Postponed`, `Cancelled`, out-of-range, class-mismatched, or frozen Sessions billable.

## Policy versions

### `legacy_session_only_v1`

Historical pre-TUITION-11 behavior. Attendance is ignored for otherwise eligible Completed Sessions.

### `attendance_v1`

Historical TUITION-11 behavior. Its meaning is frozen and must not be changed:

| Attendance | Billable |
| --- | --- |
| Present | Yes |
| Late | Yes |
| Absent | Yes |
| Excused | No |
| Missing | Yes |
| Unknown | No |

`Excused` therefore remains a waiver only for Enrollment rows that already snapshot `attendance_v1`.

### `attendance_v2`

Current policy for newly created Enrollment rows:

| Attendance | Billable | Meaning |
| --- | --- | --- |
| Present | Yes | Delivered session is billable. |
| Late | Yes | Delivered session is billable. |
| Absent | Yes | Reserved/delivered session remains billable. |
| Excused | Yes | Excused absence does not waive tuition. |
| Missing | Yes | Missing attendance cannot silently erase a receivable. |
| Unknown | No | Unknown future values fail closed. |

## Historical auditability

TUITION-18 requires no data migration. Existing database rows retain their persisted policy version (`legacy_session_only_v1` or `attendance_v1`). Only newly inserted Enrollment rows receive the model default `attendance_v2`.

This avoids retroactively increasing historical receivables for Enrollment contracts that were created under the explicit TUITION-11 waiver semantics.

## Ledger boundary

No tuition-adjustment compensation is created. TUITION-11 represented `Excused` as a dynamic accrual decision, not as a persisted waiver/credit ledger row. Creating a compensating finance adjustment would therefore duplicate accounting effects and violate source-of-truth ownership.

## Calculation ownership

`BillableSessionPolicy` remains the sole SessionStatus × AttendanceStatus policy owner. `TuitionAccrualService` consumes that decision; Outstanding and Tuition Detail continue consuming the accrual result. UI code must not reproduce the billing matrix.
