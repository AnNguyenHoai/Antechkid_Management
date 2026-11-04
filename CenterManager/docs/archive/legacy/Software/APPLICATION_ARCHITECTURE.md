# APPLICATION_ARCHITECTURE.md

Version: 1.0

Status: APPROVED

Architecture Level: Software

Depends On

- ARCHITECTURE_V2.md
- WORKSPACE_SPEC.md
- INFORMATION_ARCHITECTURE.md
- DOMAIN_MODEL.md

---

# 1. Purpose

This document defines the software architecture of CenterManager.

It specifies:

- Application Layers
- Module Structure
- Dependency Rules
- State Management
- Service Organization
- Repository Pattern
- Communication Flow

This document does NOT define:

- UI Design
- Database Schema
- API Specification
- Deployment

---

# 2. Architecture Philosophy

CenterManager follows a layered architecture.

Business logic is independent from UI.

Infrastructure is replaceable.

Every Workspace follows the same architecture.

The software architecture should remain stable as the product grows.

---

# 3. High-Level Architecture

```
+--------------------------------------------------+
|                Presentation Layer                |
|  Screens · Components · Widgets · Navigation     |
+--------------------------------------------------+
|                Application Layer                 |
|  Use Cases · Controllers · View Models           |
+--------------------------------------------------+
|                  Domain Layer                    |
|  Aggregates · Services · Business Rules          |
+--------------------------------------------------+
|              Infrastructure Layer                |
| Repository · API · Database · Storage            |
+--------------------------------------------------+
```

Dependencies only flow downward.

---

# 4. Layer Responsibilities

## Presentation Layer

Purpose

Display information and receive user input.

Contains

- Screens
- Components
- Navigation
- Forms
- Dialogs

Must NOT

- Query database
- Contain business rules
- Modify repositories directly

---

## Application Layer

Purpose

Coordinate business operations.

Contains

- Use Cases
- Controllers
- View Models
- Application Services

Responsibilities

- Call Domain
- Handle workflows
- Coordinate repositories
- Manage state transitions

---

## Domain Layer

Purpose

Represent business knowledge.

Contains

- Aggregates
- Domain Services
- Domain Events
- Business Rules
- Value Objects

Must NOT know

- Flutter
- React
- Database
- HTTP
- UI

---

## Infrastructure Layer

Purpose

Provide technical implementation.

Contains

- API Clients
- Repository Implementations
- Database Access
- Local Storage
- Authentication Provider
- File Storage

Infrastructure depends on Domain—not the reverse.

---

# 5. Workspace Module Structure

Every Workspace follows the same internal organization.

```
student/

    presentation/

    application/

    domain/

    infrastructure/

teacher/

    presentation/

    application/

    domain/

    infrastructure/

finance/

    presentation/

    application/

    domain/

    infrastructure/
```

Each Workspace is self-contained.

---

# 6. Dependency Rules

Allowed

```
Presentation

↓

Application

↓

Domain

↓

Infrastructure
```

Forbidden

```
Presentation

↓

Repository
```

Forbidden

```
Domain

↓

UI
```

Forbidden

```
Domain

↓

Database
```

Forbidden

```
Infrastructure

↓

Presentation
```

---

# 7. Communication Flow

A typical request flows through the layers.

```
User

↓

Screen

↓

ViewModel

↓

Use Case

↓

Domain Service

↓

Repository

↓

Database

↓

Repository

↓

Use Case

↓

ViewModel

↓

Screen
```

Every feature follows this pattern.

---

# 8. State Management

State belongs to the Application Layer.

Examples

- Current Student
- Current Session
- Current Workspace
- Filters
- Selected Class

Business objects remain immutable when possible.

---

# 9. Repository Pattern

Repositories abstract data access.

Examples

```
StudentRepository

CourseRepository

ClassRepository

SessionRepository

InvoiceRepository

TeacherRepository
```

Repositories expose business objects—not database tables.

---

# 10. Use Case Pattern

Every business action is represented by a Use Case.

Examples

Student

- CreateStudent
- UpdateStudent
- ArchiveStudent

Teaching

- CreateSession
- SubmitAttendance
- PublishHomework

Finance

- CreateInvoice
- RecordPayment

HR

- AssignTeacher
- ApproveLeave

Use Cases coordinate Domain logic.

---

# 11. Domain Service Pattern

Domain Services contain business logic involving multiple entities.

Examples

AttendanceService

EnrollmentService

InvoiceService

PayrollService

SessionService

Services never depend on UI.

---

# 12. Event Flow

The application uses Domain Events for cross-domain communication.

Example

```
SessionCompleted

↓

AttendanceSubmitted

↓

StudentTimelineUpdated
```

Another example

```
InvoicePaid

↓

Finance Domain

↓

Student Payment Status Updated
```

Events reduce coupling between Domains.

---

# 13. Folder Structure

```
src/

    core/

    shared/

    modules/

        student/

        teacher/

        finance/

        hr/

        report/

        admin/

    app/
```

Core contains shared infrastructure.

Modules contain business capabilities.

---

# 14. Shared Layer

Shared contains reusable elements.

Examples

```
shared/

    widgets/

    components/

    dialogs/

    utils/

    theme/

    constants/

    localization/
```

Shared must not contain business logic.

---

# 15. Core Layer

Core provides application-wide services.

Examples

```
core/

    auth/

    network/

    storage/

    routing/

    logging/

    configuration/

    security/
```

Core should remain independent from business domains.

---

# 16. API Layer

API Clients belong to Infrastructure.

Example

```
StudentApi

CourseApi

FinanceApi

HRApi
```

API Clients map transport models to Domain Models.

---

# 17. Data Mapping

External models must never enter the Domain directly.

```
API DTO

↓

Mapper

↓

Domain Object

↓

Use Case
```

Reverse

```
Domain Object

↓

Mapper

↓

DTO

↓

API
```

This isolates business logic from transport formats.

---

# 18. Error Handling

Errors are categorized into:

- Validation Errors
- Business Rule Violations
- Network Errors
- Authentication Errors
- System Errors

Presentation displays errors.

Domain defines business violations.

Infrastructure reports technical failures.

---

# 19. Testing Strategy

Each layer has its own testing scope.

Presentation

- Widget Tests
- UI Tests

Application

- Use Case Tests

Domain

- Business Rule Tests

Infrastructure

- Repository Tests
- API Integration Tests

Business rules should be testable without UI.

---

# 20. Extension Strategy

To add a new Workspace:

1. Create a new module.
2. Follow the standard folder structure.
3. Implement Presentation, Application, Domain, Infrastructure.
4. Register routing.
5. Register permissions.
6. Register navigation.

No existing Workspace should require modification.

---

# 21. Architecture Principles

Principle 1

Business logic belongs to the Domain Layer.

---

Principle 2

Presentation only displays data.

---

Principle 3

Application orchestrates workflows.

---

Principle 4

Infrastructure provides technical capabilities.

---

Principle 5

Dependencies always point inward.

---

Principle 6

Each Workspace is independently maintainable.

---

Principle 7

Shared code should contain reusable technical components—not business rules.

---

# 22. Developer Checklist

Before implementing a feature:

□ Which Workspace owns this feature?

□ Which Aggregate is affected?

□ Is a new Use Case required?

□ Which Repository is used?

□ Does this introduce a new Domain Event?

□ Does it violate any dependency rules?

□ Can the Domain be tested without UI?

□ Does it follow the standard module structure?

---

# Application Architecture Status

Version

1.0

Status

APPROVED

Frozen

YES