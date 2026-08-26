# STUDENT-1.7 — Student Workspace Integration Audit

## Scope
Audit the cross-layer Student Workspace lifecycle:

1. Student aggregate changes → dirty tracking → successful publish → latest report.
2. Parent changes are mapped to their owning Student aggregate.
3. Profile-image changes publish a complete StudentUpdated event.
4. Reports resolve profile images from runtime Attachment storage.
5. Successful publish and forced cancel clean transaction snapshots.
6. Failed publish retains recovery state.
7. Student lifecycle changes participate in aggregate tracking.
8. Archived filtering remains explicitly covered.
9. Report policy remains latest-only rather than historical accumulation.

## Runtime contract
Reports are generated only after publish success. Dirty student IDs are copied before
transaction reset can clear lifecycle state. Report failures are isolated per student and
logged without changing a successfully published transaction into a failed one.
