# CLASS-1.5 — FINAL AUDIT & REGRESSION

## Audit scope

The Class Workspace was audited across:

- CRUD and lifecycle
- archive/restore dependency policy
- teacher assignment integration
- enrollment integration
- session integration
- EventBus propagation
- cross-page refresh
- local dialog refresh
- no-op mutation behavior

## Final invariants

### Events

Domain events are emitted only for real committed mutations.

- No-op `update_class()` returns without `ClassUpdated`.
- Create/update/archive/restore events are emitted after persistence.
- Session delete event is emitted after delete commit.
- Enrollment and assignment facades preserve the shared EventBus.

### UI

Navigation and header signals are connected exactly once.

Class local mutation refresh and EventBus cross-workspace refresh remain
separate responsibilities:

- dialog signal → immediate local detail refresh
- domain event → cross-page / cross-workspace refresh

### Lifecycle

Archived classes preserve historical dependencies but reject operational
mutations until restored.

## Test environment note

The repository-wide test suite in the current execution environment cannot
collect all tests because PySide6 is not installed. Focused Class Workspace
regression tests remain executable because they validate the implemented
contracts without requiring the unavailable GUI runtime.
