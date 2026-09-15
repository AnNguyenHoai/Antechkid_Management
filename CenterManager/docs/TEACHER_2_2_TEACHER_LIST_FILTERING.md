# TEACHER-2.2 — Teacher List Filtering

## Goal

Complete the Teacher List filtering workflow without adding new repository or
service queries.

## Filters

### Status

- Active
- Inactive
- Archived
- All Current

Archived remains a separate lifecycle source and loads archived teachers through
`TeacherService.list_archived_teachers()`.

### Assignment

- All Assignments
- Has Classes
- No Classes

Assignment filtering is performed against the already-loaded
`teacher.assigned_classes` relationship.

## Composition

Status and assignment filters compose before search and sort:

```text
Loaded Teachers
    ↓
Status Filter
    ↓
Assignment Filter
    ↓
Search
    ↓
Sort
    ↓
Table
```

Changing only the assignment filter re-filters the loaded list and does not
trigger an unnecessary service refresh.
