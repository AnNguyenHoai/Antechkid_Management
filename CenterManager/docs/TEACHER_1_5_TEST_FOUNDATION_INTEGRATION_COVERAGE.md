# TEACHER-1.5 — Test Foundation & Integration Coverage

## Goal

TEACHER-1.5 strengthens the test foundation around the architecture completed in
TEACHER-1.1 through TEACHER-1.4.

This task intentionally focuses on contract and integration boundaries rather
than adding a second implementation of Teacher behavior inside tests.

## Coverage added

### Service contracts
Verifies that the core public service APIs exist for:

- Teacher lifecycle
- Teacher assignment
- Teacher documents

### Mutation contract
Verifies the architectural invariant:

```text
Persist
→ Commit
→ Publish Event
```

across Teacher mutation services.

### Event coverage
Verifies the Teacher event contract remains exported and available.

### Storage hardening
Verifies document storage protections remain present:

- unique storage names
- upload compensation
- post-commit delete cleanup
- filesystem cleanup boundaries

### UI dependency boundary
Verifies Teacher Workspace UI does not recreate production DB engines/sessions.

### Write safety
Verifies document and teacher mutation paths retain explicit write gating.

## Test strategy

These tests are deliberately lightweight and stable. They protect architectural
contracts and integration boundaries without requiring PySide6 rendering or a
live production database.

Behavior-level database integration tests can be added later using a dedicated
temporary SQLite fixture if the project standardizes a shared test database
fixture.

## Regression scope

Teacher 1.1 → 1.5 focused regression is the acceptance suite for the current
Teacher Workspace foundation.
