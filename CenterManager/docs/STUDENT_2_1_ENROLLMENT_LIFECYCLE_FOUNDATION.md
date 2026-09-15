# STUDENT-2.1 — Enrollment Domain Lifecycle Foundation

## Decision
Enrollment is the canonical Student ↔ Class relationship. Historical enrollment rows are preserved.

## Lifecycle
ACTIVE → COMPLETED
ACTIVE → WITHDRAWN

Terminal states cannot transition again.

## Implemented
- EnrollmentStatus enum.
- EnrollmentService with enroll, withdraw, complete and history queries.
- ACTIVE-only duplicate validation.
- ACTIVE-only class capacity counting.
- ACTIVE-only operational student lists.
- Existing ClassService APIs remain compatibility facades.
- Legacy remove_student no longer hard-deletes enrollment history.

## Compatibility
Existing callers can continue using ClassService.enroll_student/remove_student/get_enrolled_students.
New lifecycle code should use EnrollmentService directly.

## Deferred
- Enrollment UI.
- Student Workspace enrollment tab.
- Attendance migration beyond existing active-enrollment semantics.
- Course aggregate.
