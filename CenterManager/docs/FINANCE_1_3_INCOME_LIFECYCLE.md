# FINANCE-1.3 — Income Lifecycle

## Lifecycle contract

`Create -> Read/List -> Update -> Soft Delete`

## Ownership rules

- Tuition, Book, Robot Kit and Material income must be linked to exactly one Student and one Class.
- Student-related income must reference an actual Enrollment.
- Other income must not be linked to Student/Class.
- Student and Class ownership is immutable during update.
- Update changes transaction attributes only: amount, payment method, date, period, receiver and note.

## Safety

- Service permissions protect create/update/delete.
- UI requires collaboration WRITE mode before mutation.
- Edit/Delete context actions are disabled when write is disabled.
- Delete is soft delete.
- Timeline events are written for create/update/delete of student-related income.

## Finance-1.3 boundary

Finance event-bus refresh is intentionally deferred to Finance-1.7.
