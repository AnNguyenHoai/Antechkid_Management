# EMPLOYEE 1.4 — Working Time / Attendance

## Purpose

Record actual employee working time as individual work blocks, with self-service booking/check-in/out and Admin/Manager management.

## Domain contract

- `EmployeeScheduleRule` / `EmployeeScheduleException` = expected working time.
- `EmployeeWorkingTimeEntry` = actual working time.
- One row represents one work block.
- Open check-in rows have `end_time = NULL` and `status = OPEN`.
- Completed rows use `BOOKED`; management can move them to `APPROVED` and month closing moves them to `LOCKED`.
- Approved/locked rows cannot be edited or deleted.

## Permissions

- `working_time.view.self`
- `working_time.view.all`
- `working_time.create.self`
- `working_time.manage`
- `working_time.lock`

Admin/Manager receive all five permissions. Employee-facing roles receive self view + self booking/check-in/out.

## UI

Employee self-service:

- Employee Workspace → Attendance.
- Monthly actual/expected/overtime/shortfall summary.
- Book Time.
- Check In / Check Out.
- Edit/Delete own unlocked entries.

Admin/Manager:

- Employee Profile → Working Time.
- View and manage selected employee's entries.
- Approve entries.
- Lock a month through the service contract.

Global READ/WRITE mode controls mutation buttons; service authorization remains authoritative.

## Payroll foundation

`monthly_summary()` compares actual minutes with the effective schedule for each calendar date. It returns:

- actual minutes
- expected minutes
- overtime minutes
- shortfall minutes
- entry count

Project assignment is intentionally not modeled in 1.4; it belongs to EMPLOYEE 1.5 and can be added to working-time entries without changing the self/all authorization model.
