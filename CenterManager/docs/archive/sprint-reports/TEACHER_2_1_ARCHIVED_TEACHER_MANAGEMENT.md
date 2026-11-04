# TEACHER-2.1 — Archived Teacher Management

## Goal

Complete the user-facing lifecycle after a Teacher is archived.

## Implemented

### Teacher list
A status selector now supports:

- Active
- Inactive
- Archived
- All Current

Archived mode loads archived teachers through `list_archived_teachers()` and
searches the loaded result locally.

### Archived actions

Archived teachers expose:

- View Teacher
- Restore Teacher

They do not expose edit/archive actions.

### Restore safety

Restore requires WRITE mode and uses the existing lifecycle service:
`TeacherService.restore_teacher()`.

### Teacher detail

The detail page can load archived teachers for read-only inspection and shows a
Restore action. While archived, edit and class assignment are disabled.

After restore, the detail reloads the current teacher and emits the normal
update signal.

## Lifecycle

```text
Current Teacher
→ Archive
→ Archived filter
→ View
→ Restore (WRITE)
→ Current Teacher
```
