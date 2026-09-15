# EP-ARCH-03.26 — Working-Time Provider Regression Fix

## Problem

After the `EmployeeWorkingTimeService` RepositoryProvider migration, the full suite had one legacy regression test that still monkeypatched removed concrete repository symbols from the service module:

- `EmployeeRepository`
- `EmployeeWorkingTimeRepository`

The failure occurred during `monkeypatch.setattr`, before the behavior under test executed.

## Resolution

The regression fixture now injects a `_FakeRepositoryProvider` into `EmployeeWorkingTimeService` and supplies the two repository doubles through:

- `employees(session)`
- `employee_working_times(session)`

This preserves the intended test behavior while testing the actual application-facing dependency boundary introduced by EP-ARCH-03.25.

No compatibility alias for concrete repositories is added to the service module. Adding such aliases would reintroduce the architecture ambiguity that the migration intentionally removed.

## Guard

A dedicated regression guard verifies that `employee_working_time_service.py` does not contain concrete repository symbols. Future tests should inject repository doubles through `RepositoryProvider` rather than monkeypatching concrete repository names inside application services.
