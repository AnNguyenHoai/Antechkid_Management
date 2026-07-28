# CenterManager — Sprint 0.2C Developer Contract

**Sprint:** 0.2C
**Name:** Database Foundation & Domain Models
**Project:** CenterManager
**Developer:** DeepSeek
**Technical Lead / Reviewer:** ChatGPT
**Product Owner:** An
**Status:** READY FOR DEVELOPMENT

---

# 1. Sprint Objective

Implement the first production-ready data layer for CenterManager.

This sprint establishes:

* SQLite database foundation.
* SQLAlchemy ORM foundation.
* 8 approved domain models.
* Model relationships.
* Database session management.
* Alembic migration system.
* Initial database migration.
* Repository foundation.
* Database integrity rules.
* Automated database tests.

This sprint DOES NOT implement UI or business features.

Expected architecture after completion:

```text
UI
 │
 ▼
Service
 │
 ▼
Repository
 │
 ▼
SQLAlchemy ORM
 │
 ▼
SQLite
 │
 ▼
center.db
```

---

# 2. Frozen Architecture

Sprint 0.1 Foundation is considered FROZEN.

Developer MUST NOT redesign:

```text
core/
database/
models/
repositories/
services/
modules/
ui/
export/
utils/
```

Existing Sprint 0.1 tests must continue to pass.

Do not bypass the architecture.

Forbidden:

```text
UI → SQLite

UI → SQLAlchemy

UI → Repository
```

Future application flow remains:

```text
UI
 ↓
Service
 ↓
Repository
 ↓
Database
```

---

# 3. Database Location

Production database:

```text
runtime/
└── Database/
    └── center.db
```

Database path MUST come from the existing centralized path system.

Do NOT hardcode:

```python
"runtime/Database/center.db"
```

or any absolute path.

---

# 4. Database Technology

Use:

```text
SQLite
SQLAlchemy
Alembic
```

Add Alembic to runtime dependencies.

Do NOT introduce:

* PostgreSQL
* MySQL
* Pydantic
* external database server
* another ORM

without Technical Lead approval.

---

# 5. Domain Schema

Implement exactly these 8 domain tables:

```text
students
parents
enrollments
assessments
timeline_events
student_products
progress
attachments
```

Do NOT add business tables beyond this list.

Alembic internal table is expected and allowed.

---

# 6. Student Model

Table:

```text
students
```

Required fields:

```text
id
student_code
full_name
preferred_name
date_of_birth
gender
status
current_level
notes
created_at
updated_at
deleted_at
```

Requirements:

### id

```text
INTEGER
PRIMARY KEY
```

Internal database identity.

Do NOT use `student_code` as PK.

### student_code

```text
TEXT
NOT NULL
UNIQUE
```

Example:

```text
HS001
HS023
HS104
```

No automatic code-generation algorithm is required in this sprint.

### full_name

```text
TEXT
NOT NULL
```

### preferred_name

Nullable text.

### date_of_birth

Nullable date.

### gender

Nullable text.

Do NOT use DB Enum.

### status

Text.

Suggested default:

```text
ACTIVE
```

Do NOT use DB Enum.

### current_level

Nullable text.

### notes

Nullable text.

### timestamps

```text
created_at
updated_at
```

required.

### deleted_at

Nullable datetime.

Used for future soft delete.

---

# 7. Parent Model

Table:

```text
parents
```

Fields:

```text
id
student_id

relationship
name
phone
email

is_primary_contact

notes

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N Parent
```

Requirements:

```text
student_id
```

must be FK to:

```text
students.id
```

`relationship` remains TEXT.

Examples:

```text
FATHER
MOTHER
GUARDIAN
OTHER
```

Do NOT use DB Enum.

`is_primary_contact`:

```text
BOOLEAN
```

default false.

---

# 8. Enrollment Model

Table:

```text
enrollments
```

Fields:

```text
id
student_id

class_name
course_name
teacher_name

level

start_date
end_date

status

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N Enrollment
```

Current enrollment will eventually be identified through:

```text
status = ACTIVE
```

Do NOT create:

```text
classes
courses
teachers
```

tables in this sprint.

Those belong to future Center Management scope.

---

# 9. Assessment Model

Table:

```text
assessments
```

Fields:

```text
id
student_id

assessment_date

cycle_months

period_start
period_end

level

strengths
areas_for_improvement
comments
recommendation

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N Assessment
```

Assessment represents HISTORY.

New assessment must NOT overwrite old assessment.

`cycle_months` should support values such as:

```text
3
6
```

Do not enforce only 3/6 at database level.

Future business validation belongs in Service layer.

---

# 10. Timeline Event Model

Table:

```text
timeline_events
```

Fields:

```text
id
student_id

event_date
event_type

title
description

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N TimelineEvent
```

Example event types:

```text
LEARNING
PROJECT
ACHIEVEMENT
NOTE
LEVEL_CHANGE
OTHER
```

Do NOT implement DB Enum.

Timeline is historical data.

---

# 11. Student Product Model

Table:

```text
student_products
```

Fields:

```text
id
student_id

title
product_type
url

completed_date

description

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N StudentProduct
```

`url` must support normal web URLs.

Examples may include:

```text
Google Drive
Scratch
GitHub
YouTube
Canva
other web platforms
```

Do NOT create platform-specific columns.

---

# 12. Progress Model

Table:

```text
progress
```

Fields:

```text
id
student_id

category
value

notes

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N Progress
```

Example:

```text
Python     60
Scratch    90
Robotics   40
```

`value` should be integer.

Do NOT enforce curriculum structure in this sprint.

Do NOT create:

```text
skills
lessons
curriculum
modules
```

tables.

---

# 13. Attachment Model

Table:

```text
attachments
```

Fields:

```text
id
student_id

file_name
file_type
relative_path

description

created_at
updated_at
```

Relationship:

```text
Student 1 ───── N Attachment
```

CRITICAL:

Only relative paths are allowed conceptually.

Example:

```text
HS023/robot_warehouse.jpg
```

Do NOT store:

```text
C:\Users\...
D:\Google Drive\...
/home/user/...
```

No file-copy/upload logic is required in this sprint.

---

# 14. Relationships

Student ORM model should expose relationships conceptually equivalent to:

```text
student.parents
student.enrollments
student.assessments
student.timeline_events
student.products
student.progress
student.attachments
```

Child models should expose:

```text
child.student
```

Use SQLAlchemy bidirectional relationships.

Avoid unnecessary eager loading.

Default lazy behavior is acceptable unless technically justified otherwise.

---

# 15. Foreign Key Integrity

SQLite foreign key enforcement MUST be enabled.

SQLite does not reliably enforce foreign keys merely because FK declarations exist.

Database initialization must execute equivalent behavior to:

```sql
PRAGMA foreign_keys = ON;
```

for database connections.

Add automated test proving FK enforcement works.

Example:

Attempting to create:

```text
Parent(student_id = nonexistent_student)
```

must fail.

---

# 16. Delete Behavior

Do NOT implement application-level Student deletion yet.

Student will eventually use:

```text
deleted_at
```

for soft delete.

For database relationships:

DO NOT configure destructive automatic cascade that would accidentally erase historical student data.

The following records are considered valuable historical data:

```text
assessments
timeline_events
student_products
attachments metadata
enrollments
```

Avoid:

```text
delete-orphan
```

on Student history relationships unless specifically justified and approved.

This sprint must prioritize data preservation.

---

# 17. Timestamp Strategy

Use a consistent timestamp strategy across models.

Required:

```text
created_at
updated_at
```

Use Python/SQLAlchemy-compatible datetime values.

For V1:

Use UTC internally.

Do NOT store localized display strings such as:

```text
27/07/2026 14:30
```

inside timestamp fields.

Formatting belongs to UI/PDF layers.

Document the chosen UTC strategy.

---

# 18. Model Base / Shared Mixins

Avoid duplicating timestamp definitions unnecessarily.

A small reusable model foundation is allowed, for example:

```text
Base

TimestampMixin
```

Potential:

```text
created_at
updated_at
```

But:

DO NOT build a complex generic domain framework.

Keep it simple.

---

# 19. Database Engine

Create database infrastructure under:

```text
src/centermanager/database/
```

Suggested responsibilities:

```text
base.py
engine.py
session.py
```

Exact file split may differ if justified.

Responsibilities:

### Base

SQLAlchemy declarative base.

### Engine

Create SQLite engine using centralized database path.

### Session

Provide controlled SQLAlchemy Session creation.

Expected future usage:

```python
with session_scope() as session:
    ...
```

or equivalent safe pattern.

Transactions must:

```text
commit on success
rollback on failure
close reliably
```

Do NOT create global long-lived Session objects.

---

# 20. Database Initialization

Application/database layer must be able to prepare:

```text
runtime/Database/
```

but schema creation should be migration-driven.

Do NOT use:

```python
Base.metadata.create_all()
```

as the production schema migration strategy.

It may be used inside isolated unit tests if technically appropriate.

Production schema must come from Alembic migration.

---

# 21. Alembic

Initialize Alembic correctly for the project.

Expected conceptual structure:

```text
alembic.ini

migrations/
├── env.py
├── script.py.mako
└── versions/
    └── 0001_initial_schema.py
```

Exact generated revision identifier may differ.

Alembic must use the same SQLAlchemy metadata as the application models.

Do NOT maintain a second independent schema definition.

---

# 22. Initial Migration

Create the first migration containing all 8 approved tables:

```text
students
parents
enrollments
assessments
timeline_events
student_products
progress
attachments
```

Migration must support:

```text
upgrade
```

and:

```text
downgrade
```

Testing must verify:

```text
empty DB
   ↓
alembic upgrade head
   ↓
8 domain tables exist
```

and preferably:

```text
alembic downgrade base
```

works in isolated test DB.

Do NOT run migration tests against production:

```text
runtime/Database/center.db
```

---

# 23. Repository Foundation

Implement a repository foundation.

At minimum create:

```text
repositories/base.py
repositories/student_repository.py
```

Do NOT implement every domain repository yet.

`StudentRepository` should support only foundation operations needed for testing:

```text
add(student)
get_by_id(id)
get_by_code(student_code)
list_active()
```

`list_active()` must exclude:

```text
deleted_at IS NOT NULL
```

Do NOT implement:

```text
search
pagination
complex filters
delete
restore
bulk operations
```

yet.

---

# 24. Repository Rules

Repository:

```text
MAY:
- query ORM
- add ORM entities
- work with Session
```

Repository:

```text
MUST NOT:
- generate PDF
- know PySide6
- perform UI validation
- contain product workflow
```

Future business logic belongs to Service.

---

# 25. Service Layer

Do NOT implement StudentService business functionality in this sprint.

The existing:

```text
services/
```

package should remain ready for the next sprint.

Database tests may use repositories directly.

---

# 26. Student Code

Do NOT implement automatic generation such as:

```text
MAX(student_code) + 1
```

in this sprint.

Reason:

Code generation has concurrency and business-rule implications.

For now tests may explicitly create:

```text
HS001
HS002
```

Student-code generation will be designed at Service level later.

---

# 27. Data Validation

Database constraints should enforce only structural integrity.

Examples appropriate at DB level:

```text
student_code NOT NULL
student_code UNIQUE
full_name NOT NULL
foreign keys
```

Business rules should NOT be embedded excessively into database schema.

For example:

Do NOT enforce:

```text
cycle_months IN (3, 6)
progress.value BETWEEN 0 AND 100
specific gender values
specific status values
```

yet.

Those belong to future Service validation.

---

# 28. Required Tests

All tests MUST use isolated temporary databases.

NEVER modify:

```text
runtime/Database/center.db
```

during automated testing.

Sprint 0.1 test-safety rules remain mandatory.

At minimum implement tests covering:

### Database

```text
engine creation
session creation
commit
rollback
foreign key enforcement
```

### Student

```text
create student
unique student_code
required full_name
timestamps
soft-delete field
```

### Relationships

Verify Student can have multiple:

```text
parents
enrollments
assessments
timeline events
products
progress records
attachments
```

### Repository

Verify:

```text
add
get_by_id
get_by_code
list_active
```

### History

Verify multiple assessments can coexist for one Student.

Verify multiple products can coexist for one Student.

### Attachment

Verify relative path can be stored.

No actual file operations required.

### Migration

Verify initial migration upgrades an empty isolated SQLite DB successfully.

---

# 29. Critical Production Safety Test

Add protection equivalent to Sprint 0.1 runtime safety test.

Before/after database tests:

```text
production runtime/Database/center.db
```

must NOT be modified.

If production DB does not yet exist, tests must not create it accidentally.

This is an explicit Acceptance Criterion.

---

# 30. Existing Tests

All Sprint 0.1 tests must continue to pass.

No existing test may be deleted simply to make the new suite green.

If an existing test genuinely needs adjustment due to approved database infrastructure, document exactly why.

---

# 31. Documentation

Create:

```text
docs/DATABASE_DESIGN.md
```

It must document:

* 8 tables.
* Fields.
* Relationships.
* Internal ID vs Student Code.
* Soft delete.
* Timestamp strategy.
* Relative attachment paths.
* History-data philosophy.
* Foreign key enforcement.
* Migration strategy.
* Repository responsibility.

Update:

```text
docs/ARCHITECTURE.md
```

only where needed to reflect implemented database foundation.

Update:

```text
docs/DEVELOPMENT_GUIDE.md
```

with:

```text
how to create database
how to run migrations
how to inspect migration status
how to create future migration
```

Do not rewrite unrelated documentation.

---

# 32. Dependency Update

Add:

```text
alembic
```

to appropriate runtime dependency file.

Do not add unnecessary dependencies.

---

# 33. Explicit Non-Goals

DO NOT implement:

```text
Student UI
Student Profile screen
StudentService workflow
Login
Authentication
Admin permissions
Teacher permissions
PDF generation
Excel generation
Attachment upload/copy
Google Drive API
Backup
Search UI
Dashboard
Attendance
Payment
Class management
Teacher management
Course management
Automatic Student Code generation
Import existing Excel data
```

Do not proactively implement future features.

---

# 34. Coding Requirements

Continue Sprint 0.1 standards:

```text
type hints
pathlib
small focused classes/functions
clear naming
controlled exception handling
test isolation
```

Follow:

```text
KISS
YAGNI
Single Responsibility
Separation of Concerns
```

Avoid generic abstractions without current use.

---

# 35. Acceptance Criteria

## AC-01

All Sprint 0.1 tests still PASS.

## AC-02

SQLAlchemy database engine works with isolated SQLite database.

## AC-03

SQLite foreign key enforcement is enabled.

## AC-04

All 8 approved ORM models exist.

## AC-05

All required relationships work.

## AC-06

`student_code` is unique and separate from internal PK.

## AC-07

Student supports `deleted_at` soft-delete field.

## AC-08

History models allow multiple records per Student.

## AC-09

Attachment stores relative path metadata only.

## AC-10

Session transaction handling supports commit and rollback safely.

## AC-11

Alembic is correctly integrated with application metadata.

## AC-12

Initial migration creates all 8 domain tables.

## AC-13

Initial migration can upgrade an empty isolated DB.

## AC-14

Migration downgrade works.

## AC-15

StudentRepository supports:

```text
add
get_by_id
get_by_code
list_active
```

## AC-16

`list_active()` excludes soft-deleted Students.

## AC-17

Automated tests never modify/create production `runtime/Database/center.db`.

## AC-18

No UI/business features outside sprint scope were implemented.

## AC-19

`DATABASE_DESIGN.md` accurately reflects implementation.

## AC-20

Full automated test suite PASS.

---

# 36. Required Verification

Developer must run:

```bash
pytest
```

and provide actual result.

Also verify migration manually or through automated tests:

```bash
alembic upgrade head
```

on a disposable/test database.

Do NOT use production data for verification.

If manually testing against runtime database, create a disposable runtime environment first.

---

# 37. Required Developer Completion Report

Return exactly these sections:

## 1. Summary

What was implemented.

## 2. Files Created

Every new file.

## 3. Files Modified

Every modified file.

## 4. Database Schema

List implemented tables and relationships.

## 5. Architecture Decisions

Any implementation choice not explicitly dictated by this contract.

## 6. Deviations

Any deviation from contract.

If none:

```text
None.
```

## 7. Migration Result

Provide:

```text
initial revision
upgrade result
downgrade result
```

## 8. Test Results

Actual:

```text
pytest
```

result.

## 9. Production Safety Verification

Confirm whether automated tests:

```text
created
modified
deleted
```

anything under production:

```text
runtime/Database/
```

Expected:

```text
NO
```

## 10. Known Issues

If none:

```text
None.
```

## 11. Acceptance Checklist

Report:

```text
AC-01 PASS
AC-02 PASS
...
AC-20 PASS
```

---

# 38. Review Gate

After completion:

```text
DeepSeek
   ↓
Completion Report
   +
Source package
   ↓
Technical Lead Review
```

Do NOT continue to Student UI.

Do NOT begin another sprint.

Technical Lead will independently review:

```text
ORM models
relationships
migration
repository
transaction safety
test isolation
database integrity
```

Only after:

```text
SPRINT 0.2C PASS
```

may development continue.

---

# END OF SPRINT 0.2C CONTRACT
