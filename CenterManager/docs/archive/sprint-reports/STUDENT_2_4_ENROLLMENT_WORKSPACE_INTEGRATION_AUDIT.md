# STUDENT-2.4 — Enrollment & Student Workspace Integration Audit

## Scope audited
1. Start Editing → enrollment mutation.
2. Dirty aggregate tracking.
3. Finish Editing → publish.
4. Post-publish latest report generation.
5. Runtime synchronization → Student Workspace reload.
6. Current Student Detail → Enrollment surface reload.
7. Failed publish safety.

## Verified flow
EnrollmentWidget
→ EnrollmentService
→ database commit
→ StudentEnrollmentChanged
→ MainWindow marks owning student dirty
→ Finish Editing
→ publish succeeds
→ dirty ids captured before transaction reset
→ one latest report generated per dirty student
→ transaction releases lock and resets

## Multi-client reload
SynchronizationCompleted refreshes the current Student Workspace.
ReloadRequired refreshes the workspace and current selected student.
StudentDetailPage.load_student() refreshes EnrollmentWidget through set_student().

## Hardening
Report provenance now uses `student_workspace_publish`, because the report may be triggered by any Student aggregate mutation including Enrollment, Parent, Profile, Assessment or Student state changes.

## Safety result
- No report is generated on failed publish.
- Enrollment event is emitted only after commit.
- Enrollment history remains preserved.
- Remote reload is wired back into the Enrollment UI.
