# STUDENT-2.0A — Academic Domain Audit & Enrollment Architecture

## Scope
Audit the existing Academic domain before implementing new Student-side enrollment
features. This task intentionally does not create a second Enrollment aggregate.

## Current implementation discovered

### Existing Enrollment
`Enrollment` already exists as the relationship between `Student` and `Class`.

Current model:
- `student_id` -> `students`
- `class_id` -> `classes` (nullable)
- legacy/denormalized snapshot fields: `class_name`, `course_name`, `teacher_name`
- `level`
- `start_date`, `end_date`
- `status`

Repositories already provide:
- existence check by `(student_id, class_id)`
- get by student
- get by class
- get by class with student

### Existing Class domain
`Class` already owns:
- name
- course (currently free text)
- dates
- capacity
- status
- sessions
- teachers
- enrollments
- timeline

`ClassService` already owns:
- enroll student
- remove student
- get enrolled students

### Existing downstream consumers
- Attendance validates enrollment through `(student_id, class_id)`.
- Class workspace already has an enrollment management dialog.
- Student owns the `enrollments` relationship.

## Architecture decision

### Canonical relationship
Do not introduce a second Enrollment entity.

Canonical model:

    Student 1 --- * Enrollment * --- 1 Class

Enrollment is the association entity and future Student Academic UI must consume this
existing relationship.

### Course
A separate `Course` aggregate does not currently exist. `Class.course` is free text.
STUDENT-2.x must therefore treat course as display metadata only. A future Course domain
may normalize it, but Student 2.0 must not silently introduce a foreign key or parallel
course model.

### Enrollment lifecycle
The current codebase has a lifecycle gap:
- enroll creates an enrollment
- remove hard-deletes it
- attendance only checks row existence
- `status` exists but is not yet the canonical lifecycle gate

Therefore STUDENT-2.1 should formalize the existing `Enrollment.status` rather than
replace the model.

Recommended canonical states:

    ACTIVE
    COMPLETED
    WITHDRAWN

`PENDING` is deferred until there is a real pre-start enrollment workflow.

Recommended transition:

    ACTIVE -> COMPLETED
    ACTIVE -> WITHDRAWN

Historical rows must be retained for COMPLETED/WITHDRAWN.

## Critical compatibility rule

Attendance must only treat ACTIVE enrollment as eligible after STUDENT-2.1. This is a
controlled migration and must be changed together with lifecycle semantics; changing the
repository query independently would break existing historical behavior.

## Data integrity risks found

1. `class_id` is nullable although Class enrollment is the canonical relationship.
2. `remove_student` hard-deletes history.
3. `exists(student_id, class_id)` ignores enrollment status.
4. Class capacity currently counts all enrollment rows.
5. Denormalized class/course/teacher fields can drift from Class data.
6. Class service mixes enrollment business logic into ClassService.
7. Class code is generated but not stored on the Class model; the displayed/generated
   code is currently only a transient value.

## Target for STUDENT-2.1

Refactor the existing Enrollment domain without changing its identity:

- Add explicit `EnrollmentStatus`.
- Make ACTIVE the default.
- Add `EnrollmentService`.
- Keep `EnrollmentRepository` as the data boundary.
- Convert removal into WITHDRAWN lifecycle operation.
- Preserve historical rows.
- Update active-only queries for capacity/attendance.
- Keep legacy snapshot fields only as compatibility fields during migration.
- Student UI reads enrollment through EnrollmentService.
- Class UI delegates enrollment lifecycle to EnrollmentService.

## Task sequence

### STUDENT-2.1
Enrollment Domain Lifecycle Foundation

### STUDENT-2.2
Student Enrollment UI

### STUDENT-2.3
Class Enrollment UI Migration

### STUDENT-2.4
Academic Summary & History

### STUDENT-2.5
Enrollment / Attendance Integration Audit

## Non-goals for 2.0
- No new Course aggregate.
- No duplicate StudentClass table.
- No finance coupling.
- No new attendance model.
- No automatic migration of old historical rows without explicit data rules.
