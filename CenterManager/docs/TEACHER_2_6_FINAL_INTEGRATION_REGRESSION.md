# TEACHER-2.6 — Final Integration & Regression

## Purpose

Close the Teacher Workspace implementation with an end-to-end integration pass
over the lifecycle contracts established in TEACHER-1.x and TEACHER-2.x.

## Covered lifecycle

```text
Create
  ↓
Current List / Details
  ↓
Edit
  ↓
Archive
  ↓
Archived List / Archived Details
  ↓
Restore
  ↓
Current Details
```

## Read-model checks

The final regression verifies that:

- archived teachers leave the current list;
- archived teachers remain available through archived queries;
- archived records are excluded from normal detail lookup;
- restored teachers return to normal detail lookup;
- `assigned_classes` remains available on Teacher list/detail read models.

## UI synchronization contract

Previous TEACHER-2.x work remains covered:

```text
Mutation
  ↓
Teacher List
  ↓
teacher_changed / teacher_updated
  ↓
TeacherWorkspaceShell
  ↓
List + Dashboard + visible Detail refresh
```

## Outcome

This task is the final regression gate for the current Teacher Workspace scope.
No new product feature is introduced.
