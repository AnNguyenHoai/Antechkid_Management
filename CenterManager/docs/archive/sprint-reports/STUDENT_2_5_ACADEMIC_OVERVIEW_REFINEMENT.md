# STUDENT-2.5 — Student Academic Overview & Enrollment History Refinement

## Goal
Refine the Student Enrollment tab into a clearer academic overview without changing the canonical Enrollment lifecycle.

## Added
- Academic Summary counters: Active, Completed, Withdrawn, Total Records.
- Rich enrollment metadata: Course, Teacher, Level.
- Start/End dates and derived duration.
- Status badges.
- Newest-first history ordering is explicitly covered by regression tests.
- Active classes are excluded from the enrollment selector to prevent a redundant UI path.

## Preserved contracts
- EnrollmentService remains the mutation authority.
- Enrollment events remain post-commit.
- Write mode is still required for Enroll, Complete and Withdraw.
- Historical rows remain preserved; no hard delete is introduced.
- Student Workspace publish/report/sync lifecycle remains unchanged.
