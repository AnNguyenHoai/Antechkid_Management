# EP-ARCH-03.25 — Employee Working Time Repository Boundary

## Objective

Move `EmployeeWorkingTimeService` behind the application-facing `RepositoryProvider` seam without changing business rules or authorization behavior.

## Dependency direction

```text
EmployeeWorkingTimeService
          |
          v
RepositoryProvider.employee_working_times(session)
          |
          v
EmployeeWorkingTimeRepository
          |
          v
SQLAlchemy Session
```

Employee identity lookup also goes through `RepositoryProvider.employees(session)`.

## Persistence moved below the service boundary

The working-time repository now owns:

- add + flush + refresh of new entries;
- check-out mutation + flush + refresh;
- booking mutation + flush + refresh;
- approval mutation + flush + refresh;
- deletion;
- month locking mutations + flush.

The service remains responsible for authentication, capability checks, scope, validation, overlap rules, and transaction completion.

## Compatibility

`EmployeeWorkingTimeService` keeps the existing constructor behavior when no provider is supplied by resolving `create_default_repository_provider()`. Tests and composition roots can inject a provider explicitly.

## Regression contract

The architecture suite verifies that:

- `EmployeeWorkingTimeService` has no concrete repository imports;
- it does not construct concrete repositories;
- its employee and working-time persistence paths use the provider;
- the provider lifecycle/completeness contract includes `employee_working_times`.
