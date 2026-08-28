# TEACHER-2.0 — Assignment Management

## Goal

Complete the end-to-end Teacher → Class assignment workflow using the existing
Teacher Assignment service and business rules.

## Implemented

### Teacher Detail
Added a `Manage Classes` entry point in the Assigned Classes section.

### Collaboration write safety
Assignment mutations now require WRITE mode in the dialog:

- Assign
- Unassign

### Lifecycle behavior

- ACTIVE teacher: assign and unassign.
- INACTIVE teacher: cannot create new assignments; can unassign existing
  assignments to clean up workload.
- ARCHIVED teacher: assignment management is blocked until restore.

The service remains the authoritative business validation layer.

### UI refresh

The dialog emits `assignments_changed` after each successful mutation. Teacher
Detail reloads the teacher aggregate and emits its normal `teacher_updated`
signal so the parent workspace can refresh dependent views.

### Repository boundary

Unassign no longer reaches into `repo._session` from the service. Assignment
lookup is exposed by `TeacherAssignmentRepository.get_assignment()`.

## Acceptance contract

```text
Teacher Detail
→ Manage Classes
→ WRITE validation
→ Assign / Unassign
→ DB commit
→ TeacherAssignmentChanged event
→ dialog signal
→ Teacher Detail refresh
```
