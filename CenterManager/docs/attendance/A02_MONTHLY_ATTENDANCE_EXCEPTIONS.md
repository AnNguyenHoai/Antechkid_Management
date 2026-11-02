# A-02 — Monthly Attendance Exceptions + CSV

Status: draft implementation; Windows CI and UAT pending.

## Business meaning
Two **independent** exception types:
- Low attendance: Present / due eligible session obligations below configurable threshold (default 80%). Late/Excused remain separately counted, **not** silently added to Present; consistent with A-01 AttendanceRate.
- Missing records: no Attendance record for an eligible student/session already due.
All view returns union; filter by either type.

The due-session cutoff is min(selected month end, today), never future sessions. Cancelled/Postponed sessions do not count. Eligible students are resolved by the A-01 canonical per-session Enrollment roster; archived and withdrawn behavior is therefore consistent with A-01, including its documented historical archive-date limitation.

## Scope
- New Class Workspace navigation page `Monthly Attendance`.
- Read-only table grouped by student+class for the selected calendar month, optional class, issue filter, attendance threshold.
- Recorded, due, present, late, absent, excused and missing counts and two distinct rates.
- CSV re-queries all matching rows (not a displayed page), with UTF-8 BOM for Excel.
- No SQLCipher mutation, schema change, grade modification or stored aggregates.
- Includes archived classes in class selector for historical visibility.

## Known bounds
- Month assignment uses the session's scheduled_date; actual_date only determines whether a lesson has occurred. Cross-month reschedules require separate business-policy review.
- Student archive has no effective timestamp; see A-01 for completed-session historical semantics.
- A student in two classes is represented separately for each class.
- Report requires attendance read permissions and follows existing Class Workspace access controls; no new mutation capability.
- Initial implementation uses a single monthly batched query, with Enrollment and Attendance prefetched for computation. Benchmark on larger data before production deployment.

## Release gates
- Full Windows CI PASS and sandbox Qt UI smoke.
- UAT: cancelled/future sessions excluded, withdrawn student mid-month, archived class, historical completed sessions, incomplete recording, threshold filter, month rollover, CSV row equality, READ mode, no new SQL writes.
- Do not auto-merge.
