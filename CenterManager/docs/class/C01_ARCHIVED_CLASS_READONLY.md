# C-01 — Archived Class READ-only historical detail

## Cause and scope
Class list intentionally included archived classes but double-click refused them. Normal `ClassService.get_class_with_details` also raises ClassNotFoundError for archived classes, while archiving withdraws all active Enrollments and the original detail student count is no longer an historical count.

## Design
- Preserve the normal active-class service contract; no global weakening of archived write restrictions.
- Add dedicated `get_archived_class_with_details` read API and `get_historical_enrolled_students` including withdrawn and completed non-reconciled Enrollment history.
- Class detail attempts active getter first and archived getter only on ClassNotFoundError. It displays an explicit **ARCHIVED · READ ONLY** header and historic roster indicator.
- All active edit, class session creation, assignment, transfer and withdrawal controls are disabled for archived classes, irrespective of current WRITE ownership.
- Archived Session Detail disables editing controls for Attendance, session edits, notes and highlights; historical data remains visible. Ordinary live WRITE enforcement is unchanged.
- Restore is still a separate authorized WRITE action. No direct DB modification, migration, archive/restore changes, or Finance/Attendance history mutation.

## Validation
- Source regression tests for list routing, service read path and read-only nesting.
- Windows full CI and two-Windows-PC sandbox UAT still required.
- Verify archived class student history, session and attendance contents, timeline, PDF export (read-only), Restore action, active class editing and READ mode.
- No production database/test account access and no auto-merge.

## Limits
Historical students displayed are deduplicated by Student ID from non-reconciled Enrollment records. A full Enrollment history table with archived/reconciled lineage and finance per-contract detail is outside C-01; Finance F-29 is independent.
