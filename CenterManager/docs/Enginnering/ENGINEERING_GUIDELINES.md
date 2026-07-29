# ENGINEERING_GUIDELINES.md

Version: 1.0

Status: APPROVED

Architecture Level: Engineering

Depends On

- ARCHITECTURE_V2.md
- DOMAIN_MODEL.md
- APPLICATION_ARCHITECTURE.md
- TECHNICAL_ARCHITECTURE.md

---

# 1. Purpose

This document defines the engineering standards of CenterManager.

It standardizes:

- Development Workflow
- Feature Development
- Code Organization
- Pull Request Process
- Review Checklist
- Engineering Principles

Every contributor must follow these guidelines.

---

# 2. Engineering Philosophy

Software should be easy to understand.

Easy to modify.

Easy to extend.

Easy to test.

We optimize for long-term maintainability rather than short-term speed.

---

# 3. Development Workflow

Every feature follows the same lifecycle.

```
Business Requirement

↓

Workspace

↓

Domain Model

↓

Use Case

↓

Implementation

↓

Testing

↓

Review

↓

Merge
```

Developers must not skip steps.

---

# 4. Feature Development Process

Before writing code, answer:

1.

Which Workspace owns this feature?

2.

Which Domain owns it?

3.

Which Aggregate is affected?

4.

Which Use Case is required?

5.

What Business Rule changes?

6.

Does it require new Domain Events?

Only then begin implementation.

---

# 5. Workspace Rule

Every feature belongs to exactly one Workspace.

Correct

```
Homework

↓

Teacher Workspace
```

Incorrect

```
Homework

↓

Teacher

↓

Student
```

Business ownership must remain clear.

---

# 6. Aggregate Rule

Every modification starts from an Aggregate Root.

Correct

```
Session

↓

Attendance
```

Incorrect

```
Attendance Repository

↓

Update Session
```

Aggregate boundaries must be respected.

---

# 7. Layer Rule

Presentation

↓

Application

↓

Domain

↓

Infrastructure

No layer may bypass another.

Forbidden

```
Screen

↓

Database
```

Forbidden

```
Controller

↓

SQL
```

---

# 8. Single Responsibility

Each class should have one responsibility.

Examples

Good

```
CreateStudentUseCase
```

Bad

```
StudentManager
```

Good

```
AttendanceService
```

Bad

```
SchoolService
```

Large "God Classes" are prohibited.

---

# 9. Naming Convention

Classes

```
Student

Session

Invoice
```

Repositories

```
StudentRepository
```

Use Cases

```
CreateStudentUseCase

SubmitAttendanceUseCase
```

Services

```
AttendanceService
```

Events

```
StudentCreated

InvoicePaid
```

Controllers

```
StudentController
```

Naming should clearly express intent.

---

# 10. Folder Rule

Never organize by technical type only.

Preferred

```
modules/

    student/

    teacher/

    finance/
```

Not

```
controllers/

repositories/

services/

models/
```

Business comes first.

---

# 11. Business Logic Rule

Business Rules belong to Domain.

Never

UI

Database

Controller

Example

Incorrect

```
if(student.age < 6)
```

inside UI.

Correct

```
Student.canEnroll()
```

inside Domain.

---

# 12. Repository Rule

Repositories

Load

Save

Delete

Query

Repositories never contain business rules.

---

# 13. Use Case Rule

Each Use Case performs one business action.

Examples

CreateStudent

ArchiveStudent

GenerateInvoice

SubmitAttendance

Avoid giant Use Cases.

---

# 14. Domain Event Rule

Whenever significant business changes occur, consider publishing an event.

Examples

StudentCreated

EnrollmentCompleted

AttendanceSubmitted

InvoicePaid

Events improve decoupling.

---

# 15. Error Handling Rule

Every Use Case returns explicit results.

Never hide failures.

Validation errors should be distinguishable from system errors.

---

# 16. Testing Rule

Every Business Rule requires automated tests.

Minimum

Unit Test

For

- Domain
- Use Case

Integration Tests

For

- Repository
- API

UI Tests

For

Critical workflows.

---

# 17. Pull Request Process

Every PR should answer:

What changed?

Why?

Business impact?

Architecture impact?

Testing evidence?

Screenshots (if UI).

---

# 18. Code Review Checklist

Reviewers verify:

□ Workspace ownership

□ Aggregate boundaries

□ Layer dependencies

□ Naming

□ Tests

□ Business rules

□ Error handling

□ Logging

□ Documentation

---

# 19. Definition of Done

A feature is complete only if:

□ Code implemented

□ Tests passing

□ Architecture respected

□ Documentation updated

□ Review approved

□ No critical issues

---

# 20. Refactoring Policy

Refactor continuously.

Do not wait for large rewrites.

Small improvements are encouraged.

Large architectural changes require approval.

---

# 21. Technical Debt

Technical debt must be visible.

If debt is introduced:

- Document it.
- Explain why.
- Create a follow-up task.

Hidden technical debt is unacceptable.

---

# 22. Documentation Rule

When introducing:

New Workspace

New Aggregate

New Domain

New Architecture Pattern

Documentation must be updated first or together with the implementation.

Code should never become the only source of truth.

---

# 23. Performance Rule

Optimize only after correctness.

Measure before optimizing.

Avoid premature optimization.

---

# 24. Security Rule

Never trust client input.

Validate at the Application Layer.

Enforce business constraints in the Domain.

Protect sensitive data in Infrastructure.

---

# 25. Engineering Principles

Principle 1

Business first.

---

Principle 2

Architecture before implementation.

---

Principle 3

Readable code over clever code.

---

Principle 4

Small components over large components.

---

Principle 5

Consistency over personal preference.

---

Principle 6

Refactor continuously.

---

Principle 7

Tests are part of the feature.

---

Principle 8

Documentation evolves with the system.

---

# 26. Decision Tree

Before implementing any feature:

```
New Requirement

        │

        ▼

Which Workspace?

        │

        ▼

Which Domain?

        │

        ▼

Which Aggregate?

        │

        ▼

Need new Use Case?

        │

        ▼

Need new Repository?

        │

        ▼

Need new Domain Event?

        │

        ▼

Implementation

        │

        ▼

Tests

        │

        ▼

Review

        │

        ▼

Merge
```

---

# 27. Definition of Excellence

Excellent software is:

Easy to understand.

Easy to test.

Easy to extend.

Easy to review.

Easy to maintain.

Excellent software is not necessarily the shortest or most clever code.

---

# Engineering Guidelines Status

Version

1.0

Status

APPROVED

Mandatory

YES