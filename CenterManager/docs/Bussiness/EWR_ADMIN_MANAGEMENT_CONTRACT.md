# EWR Admin Management Contract

## Purpose

Define the administrative boundary for Employee Work Registration and Employee data. This contract is the foundation for the later Admin UI implementation and for the Monthly-to-Weekly registration redesign.

## Actors

- **Employee**: operates on their own work registration.
- **Manager**: performs operational team review according to the existing `work_registration.view.all` / `work_registration.manage` permissions.
- **Admin**: system-level operator. Admin is not an Employee identity and has administrative override capability.

## Registration Period

The current period model remains monthly in this contract (`year + month`). A separate task will migrate the period model to weekly after this boundary is stable.

Normal lifecycle:

```text
OPEN -> CLOSED
```

`CLOSED` means ordinary operational users can no longer edit the period or its registrations.

### Admin override

An Admin may reopen a `CLOSED` period through an explicit administrative operation:

```text
CLOSED --ADMIN OVERRIDE--> OPEN
```

A reopen requires a non-empty reason and creates an audit record containing actor, target period, old state, new state, and reason.

The existing normal close/accept workflow is not bypassed for ordinary users.

## Registration Deletion

An Admin may delete a registration aggregate regardless of whether its period is `OPEN` or `CLOSED`.

Deleting a registration also removes its registration blocks through the existing ORM aggregate cascade. It does **not** delete the registration period.

A non-empty deletion reason is mandatory and the delete is audited before the transaction commits.

Deletion of the registration must not delete its historical audit records.

## Employee Deletion

An Admin may hard-delete an Employee only when the Employee has no operational history:

- work registrations;
- schedule rules;
- schedule exceptions;
- working-time entries.

If any of these records exist, hard deletion is rejected and the Employee must be archived using the existing Employee status lifecycle. This protects historical operational data from destructive deletion.

A non-empty deletion reason is mandatory and the delete is audited.

## Stable Administrative Capabilities

The implementation exposes these stable capability names for future permission/UI wiring:

- `work_registration.period.admin_override`
- `work_registration.delete`
- `employee.delete`

The current contract restricts these operations to the Admin system role. Existing Manager permissions remain unchanged.

## Audit Actions

- `WORK_REGISTRATION_PERIOD_ADMIN_REOPENED`
- `WORK_REGISTRATION_ADMIN_DELETED`
- `EMPLOYEE_ADMIN_DELETED`

All three actions use the existing `AuditService.record_in_session()` transaction boundary.

## Non-goals

This task does not:

- migrate Monthly periods to Weekly periods;
- change the Employee identity rule (`Admin != Employee`);
- add Admin UI buttons/dialogs;
- change ordinary Employee/Manager Work Registration permissions;
- delete or rewrite existing audit history.
