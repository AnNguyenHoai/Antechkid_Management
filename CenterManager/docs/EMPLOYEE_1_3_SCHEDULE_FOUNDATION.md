# EMPLOYEE 1.3 — Schedule Foundation

## Purpose
Define expected employee working time separately from actual Working Time. Schedule is management-owned data and is read-only for self-service employees.

## Scope
- Recurring weekly schedule rules.
- Effective-from/effective-to dates.
- Multiple non-overlapping time blocks per day.
- One date exception per employee/date.
- Exception types: OFF, MODIFIED, HOLIDAY, LEAVE.
- Admin/Manager management; employee self read-only.
- Global READ/WRITE state controls schedule mutation in UI.

## Domain contract
`EmployeeScheduleRule` stores expected recurring blocks. `EmployeeScheduleException` overrides the weekly rule for a specific date.

`Schedule != Working Time`: Schedule is expected time; Working Time will record actual time in EMPLOYEE 1.4.

## Authorization
- Admin/Manager: view all and manage schedules.
- Other employee roles: view own schedule only.
- Service layer enforces employee ownership; UI restrictions are not the security boundary.

## Future payroll use
Schedule will later provide expected hours against which actual Working Time can be compared for regular hours, missing time and overtime. Effective dating preserves historical payroll interpretation.
