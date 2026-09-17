# EP-PROTOTYPE-06 — Session / Operational Workspace

## Purpose
Freeze the existing session-level operational flow as the next Prototype contract without introducing a second routing or service architecture.

## Golden Flow

`Class Detail → Schedule → Session Detail → Attendance / Teaching Overview → back to Class`

## Contract

1. **Session entry remains class-owned**
   - Sessions are discovered from the Class Workspace schedule.
   - `ClassScheduleWidget` loads sessions for the selected class through `SessionService`.

2. **Session detail is the operational workspace**
   - `SessionDetailDialog` is the existing session-level workspace.
   - It exposes the selected session context and keeps session operations together.

3. **Attendance is first-class**
   - Session detail exposes an Attendance tab backed by `SessionAttendanceWidget`.
   - Attendance changes refresh the session-level summary.

4. **Teaching context is first-class**
   - Teaching Overview exposes session header/status, attendance summary, notes, highlights and a compact summary.
   - Notes and student highlights remain session-scoped.

5. **Session lifecycle remains explicit**
   - Add/edit uses `SessionDialog` and `SessionService`.
   - Existing validation and permission boundaries remain owned by the service layer.

6. **Class/session context is preserved**
   - Session detail is opened with the selected session ID.
   - The session resolves its class ID through the session model/service boundary.

7. **Reporting remains operational and read-only**
   - Class schedule exposes manual session PDF export.
   - Export does not become a write-mode mutation.

8. **No second router/service layer**
   - Do not introduce a second Session Workspace router.
   - Do not duplicate `SessionService`, repositories, or application navigation.
   - Existing Class Workspace remains the entry point for session discovery.

## Non-goals

- No production refactor solely for this prototype contract.
- No new session aggregate or repository abstraction.
- No replacement of the existing modal session-detail workspace.
- No change to business behavior.

## Completion Gate

The implementation passes the source-driven regression test for this contract and the existing test suite remains green.
