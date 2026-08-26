# STUDENT-1.9 — Stability / Regression Gate

## Goal
Close the Student Workspace profile lifecycle with a focused regression gate before
new academic-domain features are introduced.

## Protected contracts
- Explicit write-transaction lifecycle.
- Report generation only after successful publish.
- Parent and profile-image changes belong to the owning Student aggregate.
- Student lifecycle changes participate in dirty tracking.
- Snapshot recovery and cleanup order remains safe.
- Latest-only report policy.
- Filter/search/sort share one filtered data base.
- Active/Archived/Deleted lifecycle filters remain supported.
- Refresh cannot retain stale bulk selections.
- Read-only users are not offered enabled mutation actions.

## Exit criteria
1. Full project test suite passes in the Windows runtime environment.
2. This regression gate passes.
3. Manual smoke test passes:
   - Add student
   - Edit student
   - Add/update parent
   - Change profile image
   - Finish editing and verify latest report
   - Archive/restore/delete lifecycle
   - Cancel editing and verify rollback
4. No unexpected ERROR/Traceback in application logs.
