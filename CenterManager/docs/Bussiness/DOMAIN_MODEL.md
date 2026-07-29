# DOMAIN_MODEL.md

Version: 1.0

Status: APPROVED

Architecture Level: Domain

Depends On

- ARCHITECTURE_V2.md
- WORKSPACE_SPEC.md
- INFORMATION_ARCHITECTURE.md

---

# 1. Purpose

This document defines the business domain model of CenterManager.

It specifies:

- Business Domains
- Aggregates
- Aggregate Roots
- Domain Relationships
- Domain Services
- Domain Events
- Business Invariants

It does NOT define:

- Database tables
- APIs
- UI
- Repository implementation

---

# 2. Domain Philosophy

CenterManager is designed using Business Domains.

Each Domain represents an independent business capability.

Domains communicate through references, services, and events.

Business rules belong to Domains—not to UI or database.

---

# 3. Domain Map

```
CenterManager

├── Student Domain

├── Teaching Domain

├── Finance Domain

├── HR Domain

├── Report Domain

└── Administration Domain
```

Every Domain owns its business rules.

---

# 4. Aggregate Design

Each Domain contains one or more Aggregates.

Aggregate = Consistency Boundary.

Only Aggregate Root can be modified directly.

Child objects are modified through the Aggregate Root.

---

# 5. Student Domain

Aggregate Root

```
Student
```

Aggregate

```
Student

├── Parent

├── Enrollment

├── Assessment

├── Timeline

├── Portfolio

└── Attachment
```

Only Student can modify its children.

Forbidden

```
Assessment Repository

↓

Modify Student
```

Correct

```
Student

↓

Assessment
```

---

# 6. Teaching Domain

Aggregate Roots

```
Course

Class

Session
```

Relationship

```
Course

└────< Class

          └────< Session
```

Session Aggregate

```
Session

├── Attendance

├── Homework

├── Teaching Note

├── Lesson Material

└── Student Highlight
```

Only Session manages its children.

---

# 7. Finance Domain

Aggregate Root

```
Invoice
```

Aggregate

```
Invoice

├── Payment

└── Discount
```

Product is an independent Aggregate.

```
Product
```

---

# 8. HR Domain

Aggregate Root

```
Employee
```

Aggregate

```
Employee

├── Teacher

├── Contract

├── Leave

└── Payroll
```

Teacher is a specialization of Employee.

---

# 9. Aggregate Relationships

Ownership

```
Course

owns

Class
```

Ownership

```
Class

owns

Session
```

Ownership

```
Session

owns

Attendance
```

Reference

```
Session

references

Student
```

Reference

```
Invoice

references

Student
```

Reference

```
Course

references

Teacher
```

Ownership never crosses Domains.

---

# 10. Domain Services

Business logic involving multiple Aggregates belongs to Domain Services.

Examples

Student Domain

- Enrollment Service
- Assessment Service

Teaching Domain

- Attendance Service
- Session Service
- Homework Service

Finance Domain

- Invoice Service
- Payment Service

HR Domain

- Payroll Service
- Leave Service

Services coordinate Aggregates but do not own data.

---

# 11. Domain Events

Domains publish events when important business actions occur.

Student Domain

- StudentCreated
- StudentUpdated
- EnrollmentCompleted
- StudentArchived

Teaching Domain

- SessionStarted
- AttendanceSubmitted
- HomeworkAssigned
- SessionCompleted

Finance Domain

- InvoiceCreated
- PaymentCompleted
- RefundIssued

HR Domain

- TeacherAssigned
- LeaveApproved
- PayrollGenerated

Events notify other Domains without transferring ownership.

---

# 12. Business Invariants

Business Invariants are rules that must always be true.

Student

- Student ID is unique.
- A Student cannot be enrolled twice in the same Class.

Course

- Every Class belongs to exactly one Course.

Class

- Every Session belongs to exactly one Class.

Session

- Attendance cannot exist without a Session.
- Homework cannot exist without a Session.

Invoice

- Payment cannot exceed the Invoice total.
- Every Payment belongs to one Invoice.

Teacher

- Every Teacher is an Employee.

These rules are enforced inside the Domain.

---

# 13. Cross-Domain Interaction

Domains interact through references and events.

Example

Student enrolls in a Class.

```
Student Domain

↓

EnrollmentCreated

↓

Teaching Domain

↓

Class references Student
```

Teaching Domain never owns Student.

---

# 14. Domain Boundaries

Each Domain has clear responsibilities.

Student Domain

- Learner information
- Parent information
- Academic history

Teaching Domain

- Teaching activities
- Courses
- Classes
- Sessions

Finance Domain

- Products
- Billing
- Payments

HR Domain

- Employees
- Teachers
- Contracts

Report Domain

- Read-only analytics

Administration Domain

- Authentication
- Authorization
- System configuration

---

# 15. Dependency Rules

Allowed

```
Teaching

↓

Student (Reference)
```

Allowed

```
Finance

↓

Student (Reference)
```

Allowed

```
Report

↓

Teaching

↓

Finance

↓

Student
```

Forbidden

```
Teaching

↓

Modify Invoice
```

Forbidden

```
Finance

↓

Modify Session
```

Forbidden

```
HR

↓

Modify Student
```

---

# 16. Aggregate Lifecycle

Every Aggregate follows a lifecycle.

```
Created

↓

Active

↓

Updated

↓

Archived
```

Deletion is discouraged.

Historical consistency must be preserved.

---

# 17. Repository Rules

One Aggregate Root has one Repository.

Examples

StudentRepository

CourseRepository

ClassRepository

SessionRepository

InvoiceRepository

EmployeeRepository

Repositories never expose child entities independently.

---

# 18. Transaction Boundary

A transaction must not span multiple Aggregate Roots unless coordinated by a Domain Service.

Example

Allowed

```
Update Session

↓

Save Attendance
```

Forbidden

```
Update Student

+

Update Invoice

+

Update Session

in one Aggregate transaction
```

---

# 19. Extension Rules

New business capabilities must follow these steps:

1. Create or identify the Domain.
2. Define Aggregate Root.
3. Define child entities.
4. Define business invariants.
5. Define domain events.
6. Expose services.
7. Update Information Architecture.

No feature should bypass this process.

---

# 20. Domain Principles

Principle 1

One Domain = One Business Responsibility.

---

Principle 2

One Aggregate Root controls its Aggregate.

---

Principle 3

Child entities never exist independently.

---

Principle 4

Domains communicate through references and events.

---

Principle 5

Business rules belong to the Domain.

---

Principle 6

UI must never enforce business invariants.

---

Principle 7

Repositories manage Aggregate Roots only.

---

# Domain Model Status

Version

1.0

Status

APPROVED

Frozen

YES