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
| `employee_schedule_service.py` | COMPLIANT | Repository dependency and mutation persistence migrated behind provider/repository. |
| `employee_work_registration_service.py` | COMPLIANT | Repository dependency and direct persistence/connection operations migrated below the service boundary. |
| `employee_admin_management_service.py` | COMPLIANT | Repository dependencies and operational-history lookup migrated behind provider. |
| `employee_document_service.py` | COMPLIANT | Repository dependency is behind provider; no concrete repository construction remains. |
| `employee_service.py` | COMPLIANT | Employee, user, and role repository dependencies migrated behind provider. |
| `employee_working_time_service.py` | COMPLIANT | Working-time repository and persistence operations migrated behind provider/repository. |
| `enrollment_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `expense_timeline_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `income_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `permission_service.py` | COMPLIANT | User, role, permission, and employee persistence/query access migrated behind provider. |
| `report_service.py` | COMPLIANT | Repository access follows the provider boundary. |
| `student_note_service.py` | COMPLIANT | Concrete repository access migrated behind provider. |
| `student_service.py` | COMPLIANT | Student repository and relation-loading persistence access migrated behind provider/repository. |
| `teacher_assignment_service.py` | COMPLIANT | Repository dependencies migrated behind provider. |
| `teacher_document_service.py` | COMPLIANT | Repository dependency migrated behind provider. |
| `teacher_service.py` | COMPLIANT | Repository dependency migrated behind provider. |

## EP-ARCH-03.24 — Migrated-service persistence closure

### EmployeeWorkRegistrationService

The service continues to own the transaction boundary and atomic audit orchestration, but no longer performs infrastructure-level transaction admission or ORM state operations itself.

```text
EmployeeWorkRegistrationService
        |
        +--> RepositoryProvider.employee_work_registrations(session)
        |             |
        |             +--> begin_write()
        |             +--> flush()
        |             +--> refresh()
        |
        +--> RepositoryProvider.employee_work_registration_periods(session)
                      |
                      +--> refresh()
                      +--> detach()
```

`Session.commit()` remains service-level transaction coordination. It is deliberately not classified as a repository persistence/query bypass: the service owns the atomic transaction that contains both the business mutation and `AuditService.record_in_session()` audit insert.

### EmployeeScheduleService

Schedule rule/exception creation, update, deletion, flush, and refresh are now delegated to `EmployeeScheduleRepository`. The service performs validation, authorization, overlap checks, and transaction coordination only.

```text
EmployeeScheduleService
        |
        v
RepositoryProvider.employee_schedules(session)
        |
        v
EmployeeScheduleRepository
        |
        v
SQLAlchemy
```

The production service also resolves its default provider through `create_default_repository_provider()` rather than constructing the infrastructure provider itself.

## EP-ARCH-03.26 — PermissionService persistence boundary

`PermissionService` is now application-facing through `RepositoryProvider`. It no longer imports or constructs concrete repositories and no longer performs direct SQLAlchemy queries.

```text
PermissionService
      |
      +--> RepositoryProvider.users(session)
      +--> RepositoryProvider.roles(session)
      +--> RepositoryProvider.permissions(session)
      +--> RepositoryProvider.employees(session)
                  |
                  v
          Concrete repositories
                  |
                  v
             SQLAlchemy
```

The service remains responsible for capability checks, account/role lifecycle validation, password/authentication rules, employee provisioning orchestration, audit orchestration, and transaction completion. Repository methods own ORM query and persistence operations.

`BaseRepository.flush()` and `BaseRepository.refresh()` provide explicit repository-level state-operation seams. `Session.commit()` remains application-service transaction coordination.

## Architecture rules

The following patterns are forbidden in migrated application services:

```python
from centermanager.repositories.foo_repository import FooRepository
FooRepository(session)
session.query(...)
session.execute(...)
session.get(...)
session.add(...)
session.delete(...)
session.flush(...)
session.refresh(...)
session.connection(...)
session.get_bind(...)
```

The following remains allowed as application transaction orchestration:

```python
session.commit()
session.rollback()
```

The following is the required persistence seam:

```python
from centermanager.repositories.provider import RepositoryProvider

repo = self._repository_provider.foo(session)
```

The provider is the application-service seam; concrete repository construction and ORM access belong below that seam.

## Remaining work

EP-ARCH-03 is not yet globally closed. The migrated-service set is now larger and hardened, but the remaining legacy services still require source-level classification and migration where they perform direct ORM/persistence work. The next work should continue to be driven by source-verified violations rather than by service names.

## Definition of done

- [x] Global inventory document exists.
- [x] Migrated services are recorded.
- [x] Boundary rules are explicit.
- [ ] Every service is source-verified against the rules.
- [ ] Every remaining direct ORM access is classified.
- [ ] Final global architecture regression test covers the complete service tree.
