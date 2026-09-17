# EP-PROTOTYPE-07 — Attendance & Assessment Operational Flow

## Purpose
Freeze the operational contract for attendance and assessment in the current prototype without introducing a second workflow/router layer.

## Attendance flow
1. Session Teaching Workspace opens with `Attendance` as the operational tab.
2. `SessionAttendanceWidget` is owned by `SessionDetailDialog`.
3. Attendance loads class-enrolled students and session attendance through `AttendanceService`.
4. Teacher can mark all present, edit status/arrival time/note, and save through `AttendanceService`.
5. Saving emits `attendance_changed` and refreshes the operational summary.
6. Student Workspace exposes a read-only attendance history/rate through `StudentAttendanceWidget`.

## Assessment flow
1. Student Workspace owns `AssessmentSection`.
2. Assessment data loads through `AssessmentService`.
3. `AssessmentSection` exposes latest assessment and history.
4. Add/edit operations use `AssessmentDialog` and delegate persistence to `AssessmentService`.
5. Validation remains service-owned via `AssessmentValidationError`.
6. Assessment changes refresh the section and emit `assessment_changed` to the owning workspace.

## Boundary contract
- UI widgets/dialogs do not create repositories or sessions.
- Attendance persistence stays in `AttendanceService`.
- Assessment persistence stays in `AssessmentService`.
- No second attendance/assessment router, workspace service, or repository is introduced.
- Student attendance history remains read-only.

## Completion gate
- Targeted EP-PROTOTYPE-07 tests pass.
- Existing regression suite remains green.
- No unrelated production behavior is changed.
