# STUDENT-2.6 — Student Report Data Contract Audit

## Decision
The current codebase contains two independent report trigger mechanisms. They are not yet one canonical contract.

## Trigger inventory

| Source | Current implementation | Trigger |
|---|---|---|
| Student Workspace publish | MainWindow post-publish callback | Every dirty Student aggregate after successful publish |
| Manual export | StudentDetailPage Export PDF | Explicit user action in write mode |
| Student ReportPolicy | StudentService._trigger_report_policy | student_updated with non-empty changes |
| Attendance/session policy | ReportPolicy | progress_50 / progress_100 |
| Daily auto report | AutoReportService | application daily run |

## Important audit findings

### F1 — Duplicate/overlapping trigger architecture
Student Workspace publish generates a report for every dirty student. ReportPolicy can also generate a report for StudentUpdated. Because StudentReportService keeps only one metadata row and one PDF, the artifact is overwritten but generation work may duplicate.

### F2 — Retry publish currently does not execute the MainWindow post-publish callback
The Finish Editing callback owns report generation. retry_publish() is called directly by the publish-failure dialog. Unless WriteTransactionManager owns a durable publish-success callback, a retry can publish successfully without generating the latest report.

### F3 — Manual Export is a mutation-side UI gate
StudentDetailPage currently requires write ownership to export a report even though export does not mutate Student data. This is a UX/permission policy question, not a data-integrity requirement.

### F4 — Daily auto report condition is effectively redundant
AutoReportService checks report_exists twice and then always generates. With singleton latest-report storage, report_exists("daily") does not prevent generation.

## Canonical trigger proposal

### Generate latest Student Profile after successful publish only for Student aggregate mutations:
- StudentUpdated
- ParentAdded / ParentUpdated / ParentDeleted
- StudentEnrollmentChanged
- StudentArchived / StudentActivated

### Do not regenerate latest Student Profile by default:
- Attendance mutation
- Session completion
- Finance payment mutation
- Assessment mutation

Those domains may receive their own specialized report triggers later if product requirements demand them.

### Manual export
Manual export should regenerate the same latest Student Profile only when explicitly requested. It should not create historical report files.

### Daily auto report
Not recommended for the singleton `StudentProfile.pdf` artifact. Keep it disabled/removed unless a separate daily-report artifact type is introduced.

## Current report data contract

### Included
- Student code, name, gender, date of birth, status, enrollment date
- Optional profile image
- Primary parent name, phone, email, address
- Current class and teacher
- Academic summary: sessions, attendance rate, latest attendance
- Finance summary: expected, paid, outstanding, latest payment
- Five latest attendance records
- Five latest teacher notes

### Important data gaps / quality issues
- Student phone/email/address fields are rendered as empty constants in the generator.
- Only the first class is treated as current in profile and academic summary.
- Enrollment lifecycle history is not represented.
- Course progress is not reliably separated from raw session totals.
- Assessment is absent.
- Multiple parents are collapsed to one primary parent.
- Attendance summary uses all attendance rows and all sessions from all enrollments without a clearly defined enrollment boundary.
- Footer always says `Trang 1` even for multi-page PDFs.

## Recommended STUDENT-2.7 implementation scope
1. Introduce an explicit StudentReportData contract.
2. Replace empty student contact constants with canonical Student fields when available.
3. Add Academic Overview: active enrollments + completed/withdrawn history summary.
4. Add latest assessment summary if Assessment belongs to the Student Profile product contract.
5. Define attendance aggregation per enrollment/class.
6. Keep one latest report artifact and one metadata row.
7. Make post-publish trigger canonical and close retry-publish/report gap.
8. Separate specialized progress/daily reports from StudentProfile.pdf.
