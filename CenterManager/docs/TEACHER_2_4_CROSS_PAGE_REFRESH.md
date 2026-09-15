# TEACHER-2.4 — Cross-Page Refresh

## Goal

Keep Teacher List and Teacher Dashboard synchronized after Teacher mutations
without requiring the user to navigate away and back.

## Implemented

TeacherListPage now emits `teacher_changed` after successful:

- create
- edit
- archive
- restore
- bulk archive

TeacherWorkspaceShell centralizes dependent refreshes:

```text
Teacher mutation
    ↓
teacher_changed / teacher_updated
    ↓
_refresh_teacher_views()
    ├── Teacher List refresh
    └── Teacher Dashboard refresh
```

Detail-page mutations and list-page mutations now use the same cross-page
refresh path.

## Non-goal

This task does not add a new global event subscription. It completes the
workspace-level UI synchronization boundary using the signals already owned by
the Teacher pages.
