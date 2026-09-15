# STUDENT-2.7 Assessment Report Dirty Tracking Fix

## Canonical flow

Assessment create/update/delete
→ database commit
→ StudentAssessmentChanged event
→ MainWindow marks owning student dirty
→ Finish Editing
→ successful publish
→ one latest StudentProfile.pdf

## Important invariant

Assessment mutation never generates StudentProfile before publish.
Failed publish generates no new report.
The existing latest-report singleton lifecycle remains unchanged.

## Covered actions

- assessment created
- assessment updated
- assessment deleted
