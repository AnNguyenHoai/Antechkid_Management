# A-01 — Session Attendance roster and denominator integrity

## Root cause

Previously `get_session_attendance_overview` used the Enrollment-derived session roster for `RosterTotal` but counted all SQL Attendance rows for `Present`/`Recorded`, even rows outside that roster. Student archiving sets `Student.status=ARCHIVED` without changing the Enrollment's session interval. A not-yet-completed class session could therefore include archived Students in its denominator. Multiple overlapping Enrollment contracts could repeat the same student in a roster.

## Implemented read behavior

- Central `_roster_students_for_session` enforces canonical Enrollment session range, deduplicates by Student ID.
- Archived Student status excludes the student from operational **not-yet-COMPLETED** sessions.
- Historical **COMPLETED** sessions retain students eligible at that session's Enrollment interval even when those students were subsequently archived. This avoids a retroactive rewrite of attendance history.
- Withdrawal effective session number and end date remain authoritative; do not infer from current ACTIVE status alone.
- `_summary_for_roster` scopes every status count, recorded rows and AttendanceRate numerator to that exact roster; out-of-roster/duplicate attendance rows are excluded from KPI and surfaced as `ExcludedRecords`, never deleted.
- Service `get_summary_for_session` and `get_session_attendance_overview` use the same projection. Existing write validation uses the same roster.

## Historical ambiguity / follow-up

Student archive presently stores current status but **not a durable archive effective session/date**; unlike Enrollment withdrawal, it does not establish when the student ceased to owe attendance. A completed session *after* the student's actual archival cannot be rigorously distinguished from a session completed before archival solely from present Student status and current Enrollment. This patch intentionally protects older completed history and avoids tuition-affecting withdrawal or schema changes. A follow-up data-contract decision is required if historical retroactive archive-effective calculations are necessary.

## Release gates

- Unit regression tests for current archived, withdrawal boundaries, completed history, orphan/duplicate Attendance rows and empty roster.
- Full Windows CI and two-machine UAT with synthetic encrypted database.
- Confirm no business row / Finance / historical Attendance mutation.
- Verify percentage UI with archived Student, archival of already-completed lessons, and incomplete class sessions.
- No auto-merge and no production DB access.
