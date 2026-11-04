# PR G — Historical Enrollment Correction & Attendance/Tuition Consistency

## Problem

Class-side enrollment skipped the canonical Enrollment pricing/effective-session
dialog. When a class already had completed sessions, a newly added student was
automatically snapshotted from the next session. Attendance, however, resolved
historical eligibility from Enrollment dates, whose start date could still be
the class start date. That allowed attendance in a session that Tuition treated
as outside the Enrollment session range.

## Fix

- Class-side enrollment now uses the same EnrollmentPricingDialog contract as
  Student Workspace.
- ClassService exposes the canonical pricing preview and forwards the operator's
  explicit Enrollment snapshot to EnrollmentService.
- Attendance uses enrolled_from_session..enrolled_until_session whenever the
  tuition-aware Enrollment snapshot is available.
- Legacy unresolved Enrollment rows keep the existing date-based fallback.
- No Attendance-to-Finance write side effect is added. Tuition and Outstanding
  remain derived from Enrollment + Session + Attendance policy.

## Expected behavior

Historical correction:
- Session #1 already happened.
- Student was omitted from the roster by mistake.
- Operator enrolls the student and explicitly selects Start from session #1.
- Attendance accepts Session #1.
- Tuition accrual includes Session #1.

Genuine mid-course join:
- Session #1 already happened.
- Student genuinely joins afterward.
- Default pricing starts at Session #2.
- Attendance rejects Session #1.
- Tuition does not accrue Session #1.
