# TUITION-18 — Attendance Billing Policy V2

## Purpose

TUITION-18 defines the canonical attendance-aware tuition rule for completed teaching sessions.

Current business rule:

- `Present` → billable.
- `Late` → billable.
- `Absent` → billable.
- `Excused` → **not billable**.
- Missing attendance → billable fallback so missing attendance cannot silently erase a receivable.
- Unknown future attendance values → fail closed.

The policy remains versioned so each Enrollment snapshots its billing-policy version and historical tuition stays auditable.

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

Historical TUITION-11 behavior:

| Attendance | Billable |
| --- | --- |
| Present | Yes |
| Late | Yes |
| Absent | Yes |
| Excused | No |
| Missing | Yes |
| Unknown | No |

### `attendance_v2`

Current policy for newly created Enrollment rows:

| Attendance | Billable | Meaning |
| --- | --- | --- |
| Present | Yes | Delivered session is billable. |
| Late | Yes | Delivered session is billable. |
| Absent | Yes | Unexcused absence still consumes the reserved teaching session. |
| Excused | No | Approved/excused absence waives tuition for that session. |
| Missing | Yes | Missing attendance cannot silently erase a receivable. |
| Unknown | No | Unknown future values fail closed. |

## Historical auditability

Existing database rows retain their persisted policy version (`legacy_session_only_v1`, `attendance_v1`, or `attendance_v2`). No finance history is deleted or rewritten by this policy correction.

`attendance_v2` was introduced in TUITION-18 and corrected before establishing a distinct historical accounting contract: its intended current business meaning is that `Excused` is non-billable.

## Ledger boundary

No tuition-adjustment compensation is created by this change. Attendance billability is an accrual decision calculated by `BillableSessionPolicy`; TUITION-11/TUITION-18 do not persist a separate waiver ledger row for `Excused`. Creating a compensating finance adjustment here would duplicate accounting effects rather than correct them.

## Calculation ownership

`BillableSessionPolicy` remains the sole SessionStatus × AttendanceStatus policy owner. `TuitionAccrualService` consumes that decision; Outstanding and Tuition Detail continue consuming the accrual result. UI code must not reproduce the billing matrix.
