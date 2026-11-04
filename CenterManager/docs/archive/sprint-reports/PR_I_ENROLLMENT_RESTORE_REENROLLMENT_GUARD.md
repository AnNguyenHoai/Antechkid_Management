# PR I — Enrollment Restore, Re-enrollment Guard & Duplicate Contract Prevention

## Problem

The Class Manage Students UI previously used Remove -> Withdraw, then a later Enroll always created a new Enrollment row.
For accidental remove/add operations this produced multiple financial contracts for the same student/class and Outstanding correctly displayed both contracts, which looked like duplicated debt.

## Domain semantics

- Withdraw: a real lifecycle transition. History, attendance, tuition and payments are preserved.
- Restore: undo an accidental withdrawal by reactivating the SAME Enrollment ID.
- Re-enroll: create a NEW Enrollment only for a genuine later participation period.

## Safety rules

1. At most one ACTIVE Enrollment exists for a student/class.
2. Separate Enrollment contracts for the same student/class must not have overlapping effective session ranges.
3. Historical contract occupancy is bounded by its withdrawal/completion end_date.
4. Tuition and Attendance must not extend beyond a historical Enrollment end_date.
5. Restore never creates a new Enrollment row and records ENROLLMENT_RESTORED in AuditLog.
6. Withdraw records ENROLLMENT_WITHDRAWN with a reason.

## UI

Manage Students now labels removal as Withdraw and explains that history is retained.
When enrolling a student with withdrawn history, the operator must explicitly choose:
- Restore existing
- Create new Enrollment
- Cancel

Restore requires a reason. Withdraw also requires a reason.

## Existing duplicate data

This PR prevents new accidental duplicate contracts. It does not automatically delete or merge existing Enrollment rows because payments may already be attributed by enrollment_id.
Existing overlapping contracts require explicit reconciliation rather than heuristic deletion.
