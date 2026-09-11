# EP-ARCH-03 — Global Service Dependency Inventory

## Purpose

This inventory records the final application-service persistence boundary after EP-ARCH-03. The target dependency direction is:

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

Application services must not import or construct concrete repositories, import SQLAlchemy directly, or perform direct session persistence/query/connection operations. Transaction completion remains an application-service responsibility.

## EP-ARCH-03.27 — Final service boundary audit

The final audit is source-driven rather than allowlist-driven. The regression gate scans every `*_service.py` in `CenterManager/src/centermanager/services/` and checks three independent boundaries:

1. **Concrete repository boundary** — no service may import or construct a concrete repository.
2. **SQLAlchemy boundary** — no service may import `sqlalchemy` directly.
3. **Session persistence boundary** — no service may call `query`, `execute`, `get`, `add`, `delete`, `flush`, `refresh`, `connection`, `get_bind`, or related persistence/ORM-state operations directly on a service-owned SQLAlchemy session.

`Session.commit()` and `Session.rollback()` are explicitly retained as application transaction orchestration and are not classified as repository bypasses.

The gate dynamically discovers the complete service tree, so adding a new service cannot silently escape the architecture check by forgetting to update a migrated-service allowlist.

## Current inventory

| Service / area | Boundary status | Evidence / action |
|---|---|---|
| `assessment_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `attendance_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `class_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `class_timeline_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `employee_schedule_service.py` | COMPLIANT | Repository boundary and persistence operations migrated. |
| `employee_work_registration_service.py` | COMPLIANT | Repository boundary and direct persistence/connection operations migrated. |
| `employee_admin_management_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `employee_document_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `employee_service.py` | COMPLIANT | Employee, user, and role access migrated behind provider. |
| `employee_working_time_service.py` | COMPLIANT | Working-time repository and persistence operations migrated. |
| `enrollment_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `expense_timeline_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `income_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `permission_service.py` | COMPLIANT | User, role, permission, and employee access migrated behind provider. |
| `report_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `student_note_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `student_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `teacher_assignment_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `teacher_document_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |
| `teacher_service.py` | COMPLIANT | Covered by global service-tree boundary gate. |

## Architecture rules

Forbidden in application services:

```python
from centermanager.repositories.foo_repository import FooRepository
FooRepository(session)

from sqlalchemy.orm import Session

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

Allowed as transaction orchestration:

```python
session.commit()
session.rollback()
```

Required persistence seam:

```python
from centermanager.repositories.provider import RepositoryProvider

repo = self._repository_provider.foo(session)
```

## Definition of done — EP-ARCH-03.27

- [x] Complete `*_service.py` tree is dynamically discovered.
- [x] Concrete repository imports/construction are globally guarded.
- [x] Direct SQLAlchemy imports are globally guarded.
- [x] Direct session persistence/query/connection operations are globally guarded.
- [x] Transaction completion is explicitly allowed as service orchestration.
- [x] Inventory is source-driven rather than allowlist-driven.
- [x] Final service-boundary architecture regression tests added.
- [x] Architecture inventory updated.

EP-ARCH-03 can now move to transaction-ownership hardening in EP-ARCH-04 after the full suite passes on this baseline.
