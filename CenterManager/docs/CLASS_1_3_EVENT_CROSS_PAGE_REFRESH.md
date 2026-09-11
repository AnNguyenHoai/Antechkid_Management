# CLASS-1.3 — EVENT & CROSS-PAGE REFRESH

## Event contract

The Class Workspace now refreshes from committed domain events rather than
depending only on local dialog callbacks.

### Class events

- `ClassCreated`
- `ClassUpdated`
- `ClassArchived`
- `ClassRestored`

### Cross-domain events affecting a class projection

- `StudentEnrollmentChanged`
- `TeacherAssignmentChanged`
- `ClassSessionChanged`

## Refresh rules

Every class-affecting event refreshes:

- Class list projection
- Class dashboard projection
- Attendance consumers via `attendance_updated`

Class detail reloads only when the event affects the currently opened class.

This prevents unrelated detail pages from being unnecessarily rebuilt.

## Thread boundary

Event handlers emit a Qt signal before touching UI. This keeps refresh delivery
safe when an event originates outside the UI thread.

## Dependency wiring

`ClassWorkspaceShell` now receives the application's:

- `NotificationService`
- `EventBus`

Class and Session services receive the shared EventBus from application startup.
