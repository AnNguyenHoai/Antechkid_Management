# STUDENT-2.7 — Student Report Architecture & Data Contract Implementation

## Canonical lifecycle
Student aggregate mutation -> dirty tracking -> successful publish/retry publish -> generate one latest StudentProfile.pdf.

## Implemented
- Manual export is read-only and does not require write ownership.
- Retry publish reuses the durable post-publish callback already stored by WriteTransactionManager.
- StudentService ReportPolicy evaluation no longer generates a pre-publish StudentProfile report.
- Report now contains all parents/guardians.
- Report academic data is based on active enrollments, with lifecycle history for active/completed/withdrawn.
- Report includes the latest assessment summary.
- Fake empty Student phone/email/address rows were removed because those fields do not exist on the canonical Student model.
- Singleton latest PDF and metadata lifecycle is preserved.

## Deliberately unchanged
Attendance, finance and assessment mutations are not newly promoted to automatic StudentProfile generation triggers in this task. Their report trigger policy remains a separate product decision.
