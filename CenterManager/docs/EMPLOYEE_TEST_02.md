# EMPLOYEE-TEST-02 — Deterministic Planning Date / Clock

## Purpose

Make employee date defaults deterministic for automated tests without changing the business behavior for normal application runs.

## Contract

- Production code obtains the current date/time through `centermanager.core.clock.get_clock()`.
- Tests may inject a `Clock` instance with fixed `now()` and `today()` values.
- Explicit `hire_date` values always win over the default clock value.
- The default hire date is the injected current local date.
- `reset_clock()` restores a system-time clock.

## Scope

This task changes only the clock seam and the EmployeeService default `hire_date` behavior. It does not change persistence schemas, employee authorization rules, UI behavior, or public employee APIs.
