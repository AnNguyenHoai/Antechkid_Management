# TEACHER-1.1 — Write Safety & Dependency Cleanup

## Implemented

### 1. Teacher Documents write safety
- Added `TeacherDocumentsWidget.set_write_enabled(enabled)`.
- Upload is disabled outside write mode.
- Document delete buttons are disabled outside write mode.
- Delete operation also has a defensive runtime write check.

### 2. Safe notification dependency
- Teacher Workspace now injects a no-op notification service instead of `None`.
- Existing denied-write notification calls no longer risk `NoneType.notify()`.

### 3. UI dependency cleanup
- Removed direct database engine/session/repository access from `TeacherDocumentsWidget`.
- Teacher code lookup now belongs to `TeacherDocumentService.get_teacher_code()`.
- Removed direct database engine/session/repository access from `TeacherAssignmentDialog`.
- Available class lookup now belongs to `TeacherAssignmentService.list_available_classes()`.

### 4. Regression coverage
Added:
`tests/test_teacher_11_write_safety_dependency_cleanup.py`

Focused result:
`4 passed`

## Full-suite environment note
The local audit environment cannot collect the full suite because PySide6 is not installed and the current baseline also has an unrelated collection error:
- `ModuleNotFoundError: No module named 'PySide6'`
- `NameError: name 'Event' is not defined` in `tests/test_student_highlight_service.py`

These occurred during full-suite collection and are outside the TEACHER-1.1 changes.
