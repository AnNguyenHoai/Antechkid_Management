# TEACHER-2.3 — Dashboard Activity Refactor

## Goal

Remove the N+1 query pattern from the Teacher Dashboard.

## Before

Recent activity was loaded as:

```text
list_teachers()
    ↓
for each teacher
    ↓
get_teacher_timeline(teacher_id, limit=5)
    ↓
merge in memory
    ↓
sort in memory
```

The assignment KPI also called the assignment service once per teacher.

## After

Recent activity is loaded through one global timeline query:

```text
TeacherTimelineService.get_recent_events(limit=10)
    ↓
TeacherTimelineRepository.get_recent_events()
    ↓
ORDER BY created_at DESC
    ↓
LIMIT 10
```

Teacher context is read from the event relationship.

The assignment KPI uses the already-loaded `assigned_classes` relationship:

```text
sum(len(t.assigned_classes) for t in teachers)
```

## Result

The dashboard keeps the same user-facing behavior while avoiding repeated
per-teacher service calls and unnecessary in-memory event merging.
