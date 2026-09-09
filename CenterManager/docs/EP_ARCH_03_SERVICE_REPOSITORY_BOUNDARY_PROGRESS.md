# EP-ARCH-03 — Service/Repository Dependency Boundary

## Vertical slice: Employee Schedule

This change migrates employee schedule persistence construction behind `RepositoryProvider` while preserving the existing `session_factory` and transaction ownership.

Architectural contract:

`EmployeeScheduleService -> RepositoryProvider -> EmployeeRepository / EmployeeScheduleRepository`

The service must not select concrete repository implementations.
