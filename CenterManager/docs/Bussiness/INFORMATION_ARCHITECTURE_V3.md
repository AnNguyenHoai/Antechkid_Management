# INFORMATION_ARCHITECTURE.md

Version: 3.0

Status: APPROVED

Architecture Level: Business

Depends On

- ARCHITECTURE_V2.md
- NAVIGATION.md
- WORKSPACE_SPEC.md

---

# 1. Purpose

This document defines every Business Object inside CenterManager.

It is the canonical source describing:

- Business Objects
- Ownership
- Relationships
- Lifecycle
- Business Boundaries

It does NOT define:

- Database
- API
- UI
- Services

Those belong to later documents.

---

# 2. Architecture Philosophy

CenterManager models a real education center.

Every real-world entity becomes a Business Object.

Examples

- Student
- Teacher
- Course
- Class
- Session
- Attendance
- Invoice

Business Objects remain stable even when UI or database changes.

---

# 3. Business Object Catalog

CenterManager currently contains the following Business Objects.

## Student Domain

- Student
- Parent
- Enrollment
- Assessment
- Timeline
- Portfolio
- Attachment

---

## Teaching Domain

- Course
- Class
- Session
- Attendance
- Homework
- Teaching Note
- Lesson Material
- Student Highlight

---

## Finance Domain

- Product
- Invoice
- Payment
- Discount
- Revenue

---

## HR Domain

- Employee
- Teacher
- Contract
- Leave
- Payroll

---

## Administration Domain

- User
- Role
- Permission
- System Setting

---

# 4. Business Object Template

Every Business Object follows the same structure.

------------------------------------------------

Business Object

Purpose

Owner Domain

Owner Workspace

Parent Object

Child Objects

References

Referenced By

Lifecycle

Permissions

Business Rules

Related Screens

Future Domain Events

------------------------------------------------

Every object in this document follows this template.

---

# 5. Student

Business Object

Student

---

Purpose

Represents one learner enrolled at the education center.

---

Owner Domain

Student Domain

---

Owner Workspace

Student Workspace

---

Parent Object

None

Student is a root entity.

---

Child Objects

- Parent
- Enrollment
- Assessment
- Timeline
- Portfolio
- Attachment

---

References

None

---

Referenced By

Teacher Workspace

Finance Workspace

Report Workspace

---

Lifecycle

Created

↓

Registered

↓

Studying

↓

Completed

↓

Archived

---

Permissions

Teacher

Read

Reception

Create / Update

Manager

Full

Finance

Read

---

Business Rules

Student cannot exist without registration.

Student history must never be deleted.

Student ID is unique.

Student status changes are recorded in Timeline.

---

Related Screens

Student List

Student Detail

Enrollment

Assessment

---

Future Domain Events

StudentCreated

StudentUpdated

StudentArchived

EnrollmentCompleted

---

# 6. Parent

Purpose

Represents a student's guardian.

Owner Workspace

Student Workspace

Parent Object

Student

Relationship

Student

1 ------ N Parent

Business Rules

At least one guardian is recommended.

One Parent may reference multiple Students.

---

# 7. Course

Purpose

Represents a teaching program.

Owner Workspace

Teacher Workspace

Parent Object

None

Child Objects

Class

References

Teacher

Business Rules

Course defines curriculum.

Course cannot directly own Sessions.

Course may contain multiple Classes.

Related Screens

Course List

Course Detail

---

Future Events

CourseCreated

CourseArchived

---

# 8. Class

Purpose

Represents one learning group.

Owner Workspace

Teacher Workspace

Parent Object

Course

Child Objects

Session

References

Teacher

Student

Business Rules

Every Class belongs to exactly one Course.

A Class may contain many Students.

A Class may have many Sessions.

---

# 9. Session

Purpose

Represents one teaching activity.

Owner Workspace

Teacher Workspace

Parent Object

Class

Child Objects

Attendance

Homework

Teaching Note

Lesson Material

Student Highlight

Business Rules

Session belongs to exactly one Class.

Attendance belongs to Session.

Homework belongs to Session.

Teaching Notes belong to Session.

---

# 10. Attendance

Purpose

Represents attendance records.

Owner Workspace

Teacher Workspace

Parent Object

Session

References

Student

Business Rules

Attendance never exists without Session.

One Student has one Attendance record per Session.

---

# 11. Homework

Purpose

Represents assignments.

Owner Workspace

Teacher Workspace

Parent Object

Session

Business Rules

Homework belongs to one Session.

Homework may be optional.

---

# 12. Teaching Note

Purpose

Teacher observations.

Owner Workspace

Teacher Workspace

Parent Object

Session

Business Rules

Teaching Notes cannot be modified after approval.

---

# 13. Product

Purpose

Educational service sold by the center.

Owner Workspace

Finance Workspace

Child Objects

Invoice

Business Rules

Products define tuition fees.

---

# 14. Invoice

Purpose

Financial document.

Owner Workspace

Finance Workspace

Parent Object

Product

Child Objects

Payment

References

Student

Business Rules

Invoice belongs to one Product.

Invoice references one Student.

Invoice owns Payments.

---

# 15. Payment

Purpose

Payment transaction.

Owner Workspace

Finance Workspace

Parent Object

Invoice

Business Rules

Payment cannot exist without Invoice.

---

# 16. Teacher

Purpose

Represents an instructor.

Owner Workspace

HR Workspace

Referenced By

Teacher Workspace

Business Rules

Teacher is an Employee specialization.

Teacher profile is maintained only in HR.

---

# 17. Relationship Diagram

```
Course

└────< Class

        └────< Session

                ├────< Attendance

                ├────< Homework

                ├────< Teaching Note

                ├────< Lesson Material

                └────< Student Highlight


Student

├────< Parent

├────< Enrollment

├────< Assessment

├────< Timeline

└────< Portfolio


Invoice

└────< Payment
```

---

# 18. Ownership Rules

Ownership

```
Course

owns

Class
```

Reference

```
Class

references

Teacher
```

Reference

```
Attendance

references

Student
```

Ownership never crosses Domains.

---

# 19. Object Lifecycle

Every object follows

Created

↓

Active

↓

Updated

↓

Archived

Deletion is discouraged.

Historical records should remain available.

---

# 20. Future Objects

The catalog is expected to grow.

Examples

Inventory

Equipment

Room

Book

Library

Campaign

Lead

Transportation

AI Lesson Plan

Certification

Every future object must follow the standard Business Object Template.

---

# Information Architecture Status

Version

3.0

Status

APPROVED

Frozen

YES