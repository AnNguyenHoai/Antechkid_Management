# TUITION-11 — Attendance-aware Billing Policy

## Purpose

Tuition billability is determined by the tuition domain, never by UI or accounting-period state. The policy is versioned on each Enrollment so a later policy change cannot silently reinterpret historical tuition.

## Evaluation order

1. The Session must be `Completed`.
2. The Session must belong to the Enrollment class and fall inside the inclusive Enrollment session range.
3. The Enrollment's snapshotted `billing_policy_version` selects the attendance rule.
4. The selected attendance rule decides whether the already-eligible Completed Session accrues tuition.

Attendance can never make `Scheduled`, `Postponed`, or `Cancelled` Sessions billable.

## Policy versions

### `legacy_session_only_v1`

Used for every Enrollment that existed before TUITION-11. Attendance is ignored, preserving the exact TUITION-05/TUITION-06 historical meaning: a Completed Session inside the Enrollment range is billable.

### `attendance_v1`

Default for new Enrollments after TUITION-11.

| Attendance | Billable | Reason |
| --- | --- | --- |
| Present | Yes | Student attended the delivered session. |
| Late | Yes | Late attendance still consumed the delivered session. |
| Absent | Yes | The delivered/reserved session remains billable. |
| Excused | No | Excused is the explicit tuition-waiver attendance state. |
| Missing | Yes | Safe fallback: incomplete attendance data must not silently erase a receivable. |
| Unknown value | No | Fail closed rather than reinterpret an unknown future policy input. |

## Historical auditability

Migration `1e10a033` adds `Enrollment.billing_policy_version` and explicitly backfills all existing rows to `legacy_session_only_v1`. It does not inspect or infer historical attendance.

New Enrollment rows use `attendance_v1`. Future policy changes must introduce a new version identifier rather than changing the meaning of an existing identifier.

## Calculation ownership

`BillableSessionPolicy` owns SessionStatus × AttendanceStatus decisions. `TuitionAccrualService` consumes that policy and remains the monetary source of truth for Outstanding and Tuition Detail read models. UI must only render service-owned results.
