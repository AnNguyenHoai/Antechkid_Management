# S-01 — Student Overview Table (read-only)

## Scope
Student Workspace > Overview: student code/name, current Student status, active enrolled classes, classes with eligible sessions in the selected month, required/present/absent/unmarked session counts, present rate and total **open receivables** by student. Year/month, status and text search filter the table. Source of truth remains A-01/A-02 per-session roster and F-29 Enrollment-scoped outstanding; there is no stored balance or mutation.

## Rules
- An attendance rate is null (shown as —) when no eligible sessions exist. Do not report 0% incorrectly.
- Archived students remain discoverable and may have collectible historical debt.
- Student monthly percentage is weighted by total eligible sessions across all classes, not an average of class rates.
- Open debt is summed as positive per-contract receivables, not offset with prepaid credit from a separate Enrollment.
- Student status comes from Student; classes column lists classes with *eligible reporting-month sessions*, not a full lifetime or current Enrollment roster.
- Active classes are derived from ACTIVE Enrollment in non-archived Classes, distinct from monthly session classes.
- Student rows whose deleted_at is set are excluded; archived status alone does not exclude.
- No SQLCipher/Income/Enrollment mutations; no WRITE authority needed.

## Validation
Windows CI and sandbox UAT required before merge. Review two separate computations for month and debt against A-02 and F-29. Test archived student, multiple class enrollment, empty month, unmarked sessions, debt from archived classes and incorrect credit netting. A full all-time current-enrollment class listing and CSV are not in S-01 scope.
