# TEACHER-1.3 — Teacher Lifecycle & Assignment Rules

## Lifecycle contract

Teacher lifecycle is intentionally separated into two concepts:

### Operational status
- `ACTIVE`: teacher can be edited and can accept new class assignments.
- `INACTIVE`: teacher remains visible and historical data is preserved, but no new class assignment can be created.

### Archive state
- `ARCHIVED` is represented by `deleted_at != None`.
- Archived teachers are hidden from normal active lists.
- Archived teachers cannot be edited or assigned to new classes.
- Restore clears `deleted_at`; the previous operational status is preserved.

## Assignment rules

New assignments require:
- Teacher exists.
- Teacher is not archived.
- Teacher status is `ACTIVE`.
- Class exists.
- Class is not archived.
- Class status is `ACTIVE`.
- Duplicate Teacher-Class assignment is rejected.

Unassignment remains allowed for existing assignments so historical/lifecycle cleanup is not blocked.

## Service additions
- `list_archived_teachers()`
- `get_archived_teacher()`

## Non-goal
No database migration is required. `status` remains stored as text for compatibility, while the Teacher model and service now own the valid lifecycle contract.
