# CenterManager — Sprint 0.3 Developer Contract

**Sprint:** 0.3
**Name:** Student Application Service & CRUD Business Logic
**Developer:** DeepSeek
**Technical Lead / Reviewer:** ChatGPT
**Product Owner:** An
**Status:** READY FOR DEVELOPMENT

---

# 1. Objective

Implement the first application/business service for CenterManager:

```text
StudentService
```

After this sprint, the application layer must support:

```text
Create Student
Get Student
Update Student
List Students
Soft Delete Student
Restore Student
Generate Student Code
```

No UI is implemented in this sprint.

Target architecture:

```text
Future UI
   │
   ▼
StudentService
   │
   ▼
StudentRepository
   │
   ▼
SQLAlchemy
   │
   ▼
SQLite
```

The Service layer owns business rules.

---

# 2. Frozen Foundations

Sprint 0.1 and Database Foundation v0.2 are FROZEN.

Do NOT redesign:

```text
core/
database/
models/
repositories/
```

Do NOT modify the approved database schema unless an actual blocker is discovered.

If a schema change appears necessary:

```text
STOP
 ↓
Document reason
 ↓
Report Technical Lead
```

Do not create an Alembic migration proactively.

---

# 3. StudentService

Create:

```text
src/centermanager/services/student_service.py
```

Conceptually:

```python
class StudentService:
    ...
```

StudentService is responsible for:

```text
Business validation
Student-code generation
Student creation
Student update
Student retrieval
Student listing
Soft deletion
Restoration
```

It must NOT know PySide6.

---

# 4. Student Code Rule

Approved V1 format:

```text
HS001
HS002
HS003
...
```

Requirements:

```text
Prefix = HS
Numeric portion = minimum 3 digits
```

Examples:

```text
1    → HS001
9    → HS009
25   → HS025
999  → HS999
1000 → HS1000
```

Do NOT impose a 999-student limit.

---

# 5. Student Code Must Never Be Reused

This is a critical business rule.

Example:

```text
Existing:

HS001
HS002
HS003
```

Soft delete:

```text
HS003
```

Next Student:

```text
HS004
```

NOT:

```text
HS003
```

Another example:

```text
HS001
HS002
HS005
```

Next code:

```text
HS006
```

Do NOT fill gaps:

```text
HS003 ❌
```

Rule:

> Student codes are permanent identities and are never recycled.

---

# 6. Code Generation Strategy

For V1, generate the next Student Code from the highest existing valid `HS<number>` code across ALL students, including soft-deleted students.

Conceptually:

```text
all student codes
      ↓
valid HS numeric codes
      ↓
MAX
      ↓
MAX + 1
```

Example:

```text
HS001
HS004
HS027

→ HS028
```

Do NOT use:

```text
COUNT(students) + 1
```

because deleted students/gaps make it unsafe.

---

# 7. Invalid / Legacy Codes

The database may eventually contain imported legacy data.

Examples:

```text
ABC
TEMP01
OLD-STUDENT
```

Student-code generation must not crash because such values exist.

For automatic HS generation:

```text
HS001     → valid
HS42      → valid
HS0007    → valid
ABC       → ignored
TEMP01    → ignored
```

Extract the numeric portion only when the entire code matches conceptually:

```text
^HS\d+$
```

Case sensitivity for generated codes:

```text
HS
```

must always be uppercase.

Do not normalize existing legacy codes in this sprint.

---

# 8. First Student

If database contains no valid HS code:

```text
next_student_code()
```

returns:

```text
HS001
```

---

# 9. Concurrency Scope

CenterManager V1 assumes:

```text
Single active writer
```

Therefore this sprint does NOT need:

```text
distributed locks
database sequences
multi-user concurrency control
network synchronization
```

However, code generation and student creation should occur in the same controlled Service transaction where practical.

Do not over-engineer concurrency.

---

# 10. Create Student

Provide a Service operation conceptually equivalent to:

```text
create_student(...)
```

Minimum input:

```text
full_name
```

Optional inputs may include approved Student fields:

```text
preferred_name
date_of_birth
gender
status
current_level
notes
```

Student code is generated automatically.

Normal UI/business callers should NOT need to provide `student_code`.

Flow:

```text
create_student
      ↓
normalize input
      ↓
validate
      ↓
generate student code
      ↓
create Student
      ↓
repository.add
      ↓
transaction commit
      ↓
return Student
```

---

# 11. Full Name Validation

`full_name` is mandatory.

Invalid:

```text
None
""
"   "
```

Before saving:

```text
"   Nguyễn Văn An   "
```

should become:

```text
"Nguyễn Văn An"
```

Do NOT aggressively modify internal whitespace or Vietnamese characters.

For example:

```text
"Nguyễn Văn An"
```

must remain intact.

---

# 12. Preferred Name

If provided:

```text
"  An  "
```

normalize to:

```text
"An"
```

Empty/whitespace-only preferred name may become:

```text
None
```

---

# 13. Other Text Fields

For appropriate optional text fields:

```text
gender
status
current_level
notes
```

basic surrounding-whitespace normalization is acceptable.

Do NOT implement complex domain validation yet.

Examples NOT required:

```text
gender must be MALE/FEMALE
level must belong to curriculum
status must belong to fixed DB enum
```

---

# 14. Default Status

New Student defaults to:

```text
ACTIVE
```

unless a valid explicit status is supplied.

Do not introduce status Enum in this sprint.

---

# 15. Get Student

Provide:

```text
get_student(student_id)
```

Normal behavior should return an active Student.

Soft-deleted Student should not be treated as an active profile by the normal getter.

Also provide an explicit mechanism if required internally to retrieve a Student including deleted records for restore operations.

Keep API naming clear.

---

# 16. Get by Student Code

Provide:

```text
get_student_by_code(student_code)
```

Normal lookup should respect active-student behavior.

Example:

```text
HS023
```

→ Student.

Do not implement fuzzy search here.

---

# 17. List Students

Provide:

```text
list_students()
```

Default:

```text
ACTIVE / non-deleted students only
```

Meaning:

```text
deleted_at IS NULL
```

Sort default:

```text
student_code ascending
```

Example:

```text
HS001
HS002
HS003
...
```

No pagination required for V1.

~100–500 students is expected.

---

# 18. Update Student

Provide operation conceptually:

```text
update_student(student_id, ...)
```

Editable fields:

```text
full_name
preferred_name
date_of_birth
gender
status
current_level
notes
```

Do NOT allow normal update operation to modify:

```text
id
student_code
created_at
deleted_at
```

`student_code` is permanent identity.

---

# 19. Partial Update

Update should support changing only supplied fields.

Example:

```text
update_student(
    15,
    current_level="Python Intermediate"
)
```

must not overwrite:

```text
full_name
date_of_birth
notes
...
```

with null/default values.

---

# 20. Update Validation

If `full_name` is explicitly updated:

```text
full_name=""
```

or:

```text
full_name="   "
```

must fail validation.

Other normalization rules should match creation behavior.

---

# 21. Soft Delete

Provide:

```text
delete_student(student_id)
```

This MUST NOT execute:

```text
session.delete(student)
```

Instead:

```text
student.deleted_at = UTC timestamp
```

Historical child records remain untouched.

After deletion:

```text
list_students()
```

must no longer return the Student.

Normal:

```text
get_student()
```

must not return the Student as active.

---

# 22. Delete Idempotency

Deleting an already soft-deleted Student should produce controlled behavior.

Preferred V1 behavior:

```text
raise business-level error
```

such as:

```text
StudentAlreadyDeletedError
```

Do not silently modify deletion timestamp repeatedly.

---

# 23. Restore Student

Provide:

```text
restore_student(student_id)
```

Behavior:

```text
deleted_at = None
```

Original:

```text
student_code
```

must remain unchanged.

Example:

```text
HS017
 ↓ delete
HS017 [deleted]
 ↓ restore
HS017
```

Do NOT generate a new code during restore.

---

# 24. Restore Active Student

Trying to restore a Student that is not deleted should produce controlled behavior.

Preferred:

```text
StudentNotDeletedError
```

---

# 25. Missing Student Behavior

Do not leak random SQLAlchemy behavior to future UI.

Introduce clear business/application exceptions.

Suggested structure:

```text
services/
└── exceptions.py
```

At minimum consider:

```text
StudentNotFoundError
StudentValidationError
StudentAlreadyDeletedError
StudentNotDeletedError
```

Exact hierarchy is developer choice but must remain simple.

Future UI should be able to do conceptually:

```python
try:
    service.update_student(...)
except StudentValidationError:
    ...
```

rather than interpreting SQLAlchemy exceptions.

---

# 26. Transaction Ownership

This is important.

The Service layer should own the complete business transaction.

Conceptually:

```text
StudentService
      │
      ├── open session
      │
      ├── repository operations
      │
      ├── business changes
      │
      └── commit / rollback
```

Do not make future UI manage SQLAlchemy sessions.

Do not expose a Session requirement to GUI callers.

Preferred future usage:

```python
student = student_service.create_student(
    full_name="Nguyễn Văn A"
)
```

NOT:

```python
with Session() as session:
    student_service.create_student(session, ...)
```

from UI.

Implementation may use injected session factory internally for testability.

---

# 27. Repository Extensions

Extend `StudentRepository` only as necessary.

Likely operations:

```text
get_by_id_including_deleted
get_by_code_including_deleted
list_all_including_deleted
get_highest_student_code
```

Exact repository API is developer choice.

Business rules such as:

```text
generate HSxxx
soft-delete policy
validation
```

must remain in Service.

Repository should remain persistence-focused.

---

# 28. No Direct ORM Query in Service Where Repository Fits

Avoid spreading:

```python
session.execute(select(Student)...)
```

through StudentService.

If Student persistence/query functionality is needed, place it in StudentRepository.

Keep:

```text
Service = business policy
Repository = persistence/query
```

---

# 29. Return Type

For Sprint 0.3, Service may return ORM Student objects.

Do NOT introduce DTO frameworks yet.

No Pydantic.

We can introduce UI ViewModels later if needed.

---

# 30. Parent / Assessment / Product Scope

Do NOT implement business services for:

```text
Parent
Enrollment
Assessment
Timeline
Product
Progress
Attachment
```

in this sprint.

Their models remain available but untouched at application level.

Sprint 0.3 focuses only on Student core lifecycle.

---

# 31. Required Tests

Add comprehensive:

```text
tests/test_student_service.py
```

All tests MUST use isolated temporary databases.

Never use production:

```text
runtime/Database/center.db
```

---

# 32. Code Generation Tests

At minimum:

```text
empty DB
→ HS001
```

```text
HS001
→ HS002
```

```text
HS001 HS002 HS003
→ HS004
```

```text
HS001 HS005
→ HS006
```

```text
HS001 HS002 HS003(deleted)
→ HS004
```

```text
ABC HS005 TEMP
→ HS006
```

```text
HS999
→ HS1000
```

Also verify generated code is uppercase.

---

# 33. Create Tests

Verify:

```text
create valid student
```

returns Student with:

```text
id
student_code
full_name
status
created_at
```

Verify:

```text
"  Nguyễn Văn A  "
```

becomes:

```text
"Nguyễn Văn A"
```

Verify blank full name fails.

Verify Student Code is generated automatically.

---

# 34. Update Tests

Verify:

```text
partial update
full-name normalization
blank full-name rejection
student_code cannot change
unmodified fields remain unchanged
```

---

# 35. Delete Tests

Verify:

```text
delete_student
```

sets:

```text
deleted_at
```

and does NOT physically delete row.

Verify:

```text
list_students
```

excludes it.

Verify normal getter excludes it.

Verify historical child record remains intact if one exists.

---

# 36. Restore Tests

Verify:

```text
restore_student
```

sets:

```text
deleted_at = None
```

and Student reappears in normal list/get operations.

Verify Student Code remains unchanged.

---

# 37. Exception Tests

Verify controlled errors for:

```text
missing Student
blank name
delete already-deleted Student
restore active Student
```

No raw SQLAlchemy exception should be required for normal business-error handling.

---

# 38. Transaction Rollback Test

Add at least one test proving:

```text
business operation
      ↓
exception
      ↓
transaction rollback
```

does not leave partial Student data committed.

---

# 39. Production DB Safety

Maintain existing production safety standard.

Running:

```text
pytest
```

must not:

```text
create
modify
delete
```

production:

```text
runtime/Database/center.db
```

Add/update safety test if necessary.

---

# 40. Documentation

Create:

```text
docs/STUDENT_SERVICE.md
```

Document:

```text
Student lifecycle
Student Code rule
Create behavior
Update behavior
Soft Delete
Restore
Business exceptions
Transaction ownership
Service vs Repository responsibility
```

Update architecture documentation only if necessary.

Do not rewrite unrelated docs.

---

# 41. Explicit Non-Goals

DO NOT implement:

```text
Student GUI
Student Profile
Dashboard
Search UI
Parent Service
Enrollment Service
Assessment Service
Timeline Service
Product Service
Progress Service
Attachment Service
PDF generation
Excel generation
Authentication
Backup
Google Drive API
Excel import
Student Code manual editing
Pagination
Advanced filtering
```

---

# 42. Acceptance Criteria

**AC-01** — Existing Foundation tests PASS.

**AC-02** — `StudentService` exists.

**AC-03** — UI-independent Service API exists.

**AC-04** — First automatic Student Code is `HS001`.

**AC-05** — Student Code increments from highest existing valid HS code.

**AC-06** — Deleted Student codes are never reused.

**AC-07** — Legacy/non-HS codes do not break generation.

**AC-08** — `HS999 → HS1000`.

**AC-09** — Create Student validates `full_name`.

**AC-10** — Create normalizes supported text fields.

**AC-11** — New Student defaults to ACTIVE.

**AC-12** — Student Code cannot be changed through normal update.

**AC-13** — Partial update works correctly.

**AC-14** — Normal get/list excludes soft-deleted Students.

**AC-15** — Soft Delete never physically deletes Student.

**AC-16** — Soft Delete preserves child/history data.

**AC-17** — Restore preserves original Student Code.

**AC-18** — Missing/invalid operations produce controlled Service exceptions.

**AC-19** — Service owns transaction lifecycle.

**AC-20** — Transaction rollback is tested.

**AC-21** — StudentRepository remains persistence-only.

**AC-22** — Automated tests never modify production DB.

**AC-23** — `STUDENT_SERVICE.md` exists.

**AC-24** — Full `pytest` suite PASS.

**AC-25** — No out-of-scope UI/feature implementation.

---

# 43. Required Completion Report

Return:

## 1. Summary

## 2. Files Created

## 3. Files Modified

## 4. StudentService API

List public operations.

## 5. Student Code Implementation

Explain generation algorithm.

## 6. Validation Rules

## 7. Soft Delete / Restore Implementation

## 8. Transaction Strategy

Explain session ownership and rollback behavior.

## 9. Repository Changes

## 10. Business Exceptions

## 11. Test Results

Provide actual:

```text
pytest
```

result.

## 12. Production DB Safety

Confirm tests do not modify production database.

## 13. Deviations

If none:

```text
None.
```

## 14. Known Issues

If none:

```text
None.
```

## 15. Acceptance Checklist

```text
AC-01 PASS
...
AC-25 PASS
```

---

# 44. Review Gate

After implementation:

```text
DeepSeek
   ↓
Source + Completion Report
   ↓
Technical Lead Review
```

Do NOT begin GUI development.

Technical Lead will independently review:

```text
Student-code generation
validation boundaries
transaction ownership
repository/service separation
soft-delete safety
restore behavior
exception design
test isolation
```

Only after:

```text
SPRINT 0.3 PASS
```

may Student UI development begin.

---

# END OF SPRINT 0.3 CONTRACT
