# TEACHER-1.2 — Teacher Service Event Contract

## Contract

Teacher domain mutations now publish explicit application events **after the database mutation commits successfully**:

- `TeacherCreated`
- `TeacherUpdated`
- `TeacherArchived`
- `TeacherRestored`
- `TeacherAssignmentChanged`
- `TeacherDocumentChanged`

## Actions

Assignment:
- `assigned`
- `unassigned`

Document:
- `uploaded`
- `deleted`

## Composition

`app.py` now injects the shared application `EventBus` into:

- `TeacherService`
- `TeacherAssignmentService`
- `TeacherDocumentService`

## Non-goal

This task does **not** add Teacher dirty tracking or Student-style report generation. Teacher currently has no concrete post-publish artifact consumer. Events are introduced as the canonical mutation contract for future consumers while timeline remains the audit/history mechanism.
