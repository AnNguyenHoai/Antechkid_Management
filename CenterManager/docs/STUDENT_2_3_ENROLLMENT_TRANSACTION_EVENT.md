# STUDENT-2.3 — Enrollment Transaction & Event Integration

## Goal
Enrollment mutations must participate in the existing write transaction and publish lifecycle.

## Canonical flow
EnrollmentWidget
→ EnrollmentService mutation
→ database commit
→ StudentEnrollmentChanged
→ MainWindow transaction handler
→ mark_student_dirty(student_id)
→ Finish Editing / Publish
→ existing post-publish latest report generation

## Rules
- Event is emitted only after database commit and refresh.
- No UI-local dirty flag is required for correctness.
- Enrollment event marks the affected Student aggregate dirty.
- Failed enrollment mutation does not publish an event.
- Existing post-publish report generation remains unchanged and is reused.

## Event
StudentEnrollmentChanged:
- student_id
- enrollment_id
- class_id
- action
- previous_status
- current_status

## Result
Enrollment changes now trigger the same dirty/publish/report lifecycle as StudentUpdated.
