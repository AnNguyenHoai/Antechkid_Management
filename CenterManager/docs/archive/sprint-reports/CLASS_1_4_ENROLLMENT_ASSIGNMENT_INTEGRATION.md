# CLASS-1.4 — ENROLLMENT & ASSIGNMENT INTEGRATION

## Goal

Class Workspace mutation paths must use the canonical Enrollment and Teacher
Assignment lifecycles while preserving EventBus propagation to every workspace.

## Canonical mutation path

### Enrollment

Class UI
→ ClassService compatibility facade
→ EnrollmentService
→ database commit
→ StudentEnrollmentChanged
→ Class / Student projections refresh

### Teacher assignment

Class UI
→ ClassService compatibility facade
→ TeacherAssignmentService
→ database commit
→ TeacherAssignmentChanged
→ Class / Teacher projections refresh

## Important rule

`ClassService` may provide compatibility methods for existing Class Workspace
callers, but it must not create isolated lifecycle services with `event_bus=None`.
Facade-created services receive the application's shared EventBus.

## Local dialog behavior

Assignment and enrollment dialogs now emit mutation signals immediately after
successful changes. The Class detail page refreshes immediately for local UX,
while EventBus remains the cross-workspace synchronization mechanism.

## Lifecycle compatibility

Enrollment removal remains a historical transition to `WITHDRAWN`, not a hard
delete. Assignment removal deletes the active assignment relation while keeping
the Teacher Timeline and Class Timeline history.
