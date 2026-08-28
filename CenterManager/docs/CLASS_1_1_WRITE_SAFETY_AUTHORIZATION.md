# CLASS-1.1 — WRITE SAFETY & AUTHORIZATION

## Scope
- All class assignment and enrollment mutations are guarded in their dialogs.
- READ mode disables mutation controls and runtime mutation attempts are rejected.
- Teacher assignment is restricted to Admin and Manager.
- Class dialogs no longer create independent production database engines.

## Authorization
Teacher assignment/unassignment requires:

Admin or Manager
+ WRITE mode.

Student enrollment/removal requires:

WRITE mode.

## Dependency cleanup
The dialogs now obtain active teachers/students through ClassService read APIs,
which use the application's configured session factory.

## Dynamic detail controls
Teacher and student action buttons are rebuilt dynamically and are now disabled
when WRITE mode is unavailable. Teacher controls additionally respect the
Admin/Manager assignment policy.
