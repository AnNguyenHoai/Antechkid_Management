# EP-ARCH-03 — Global Service Dependency Inventory

## Purpose

This inventory records the dependency-boundary status of application services after the EP-ARCH-03 migrations. The target dependency direction is:

```text
Application Service
        |
        v
RepositoryProvider
        |
        v
Concrete Repository
        |
        v
SQLAlchemy / Database
```

Application services must not import or construct concrete repositories, and must not bypass the repository boundary with direct persistence/ORM access.

## Audit scope

Scope: `CenterManager/src/centermanager/services/` and the repository-provider boundary used by those services.

The audit distinguishes four cases:

- **COMPLIANT** — service persistence access is mediated by `RepositoryProvider`/repository contracts.
- **VIOLATION** — service directly imports/constructs a concrete repository or performs persistence/ORM work itself.
- **INTENTIONAL** — access is explicitly part of an infrastructure/application composition responsibility and is documented as such.
- **FOLLOW-UP** — a dependency requires source-level review before classification.

## Current inventory

| Service / area | Boundary status | Evidence / action |
|---|---|---|
| `assessment_service.py` | COMPLIANT | Repository access migrated behind provider. |
| `attendance_service.py` | COMPLIANT | Repository access migrated behind provider. |
| `class_service.py` | COMPLIANT | Concrete repository dependencies migrated behind provider. |
| `class_timeline_service.py` | COMPLIANT | Concrete repository dependency migrated behind provider. |
| `employee_schedule_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `employee_work_registration_service.py` | FOLLOW-UP | Repository dependency is behind provider; final review of transaction/direct-session operations remains. |
| `employee_admin_management_service.py` | COMPLIANT | Repository dependencies and operational-history lookup migrated behind provider. |
| `employee_document_service.py` | COMPLIANT | Repository dependency is behind provider; no concrete repository construction remains. |
| `employee_service.py` | COMPLIANT | Employee, user, and role repository dependencies migrated behind provider. |
| `enrollment_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `report_service.py` | COMPLIANT | Repository access follows the provider boundary. |
| `student_note_service.py` | COMPLIANT | Concrete repository access migrated behind provider. |
| `student_service.py` | COMPLIANT | Student repository and relation-loading persistence access migrated behind provider/repository. |
| `teacher_assignment_service.py` | COMPLIANT | Repository dependencies migrated behind provider. |
| `teacher_document_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `teacher_service.py` | COMPLIANT | Teacher repository dependency migrated behind provider. |

## EP-ARCH-03.23 — EmployeeService migration

`EmployeeService` is now application-facing through `RepositoryProvider` for all repository dependencies:

```text
EmployeeService
      |
      +--> RepositoryProvider.employees(session)
      +--> RepositoryProvider.users(session)
      +--> RepositoryProvider.roles(session)
                  |
                  v
          Concrete repositories
                  |
                  v
             SQLAlchemy
```

The service continues to own business validation, capability checks, employee identity repair, account/employee orchestration, and transaction coordination. The migration does not change those domain responsibilities.

## Architecture rules

The following patterns are forbidden in migrated application services:

```python
from centermanager.repositories.foo_repository import FooRepository
FooRepository(session)
```

and direct persistence operations such as:

```python
session.query(...)
session.execute(...)
session.scalar(...)
session.get(...)
```

when they represent repository persistence/query responsibilities.

The following is allowed:

```python
from centermanager.repositories.provider import RepositoryProvider

repo = self._repository_provider.foo(session)
```

The provider is the application-service seam; concrete repository construction belongs below that seam.

## Required follow-up audit

Before EP-ARCH-03 can be marked complete, the remaining `FOLLOW-UP` areas must be source-audited and either migrated or explicitly documented as intentional infrastructure access. The final architecture gate should scan the complete service tree for concrete repository imports/construction and direct ORM persistence access.

## Definition of done

- [x] Global inventory document exists.
- [x] Migrated services are recorded.
- [x] Boundary rules are explicit.
- [ ] Every service is source-verified against the rules.
- [ ] Every remaining direct ORM access is classified.
- [ ] Final global architecture regression test covers the complete service tree.
