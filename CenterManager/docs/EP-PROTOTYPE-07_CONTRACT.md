# EP-PROTOTYPE-07 — Attendance & Assessment Operational Flow

The prototype contract keeps attendance operational inside the Session Teaching Workspace and assessment operational inside the Student Workspace.

- SessionDetailDialog owns SessionAttendanceWidget.
- Attendance editing persists through AttendanceService.
- StudentAttendanceWidget is read-only.
- AssessmentSection owns latest/history presentation.
- AssessmentDialog persists through AssessmentService and surfaces AssessmentValidationError.
- No duplicate attendance/assessment router, service, or repository layer is introduced.
