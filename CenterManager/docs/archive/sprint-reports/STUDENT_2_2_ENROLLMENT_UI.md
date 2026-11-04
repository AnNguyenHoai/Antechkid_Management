# STUDENT-2.2 — Student Enrollment UI

## Implemented
Student Detail now includes an Enrollment tab with:
- Current active enrollment.
- Academic history for COMPLETED and WITHDRAWN enrollments.
- Enroll into an active class.
- Complete active enrollment.
- Withdraw active enrollment.

## Write contract
All enrollment mutations are disabled in READ mode and require Start Editing.

## Data contract
The UI uses the canonical EnrollmentService introduced by STUDENT-2.1.
Historical enrollment rows are never deleted by the UI.

## Wiring
EnrollmentService is created during application bootstrap and injected through:
App → MainWindow → StudentWorkspaceShell → StudentDetailPage → EnrollmentWidget.
