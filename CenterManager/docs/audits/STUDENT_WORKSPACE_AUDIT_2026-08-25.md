# Student Workspace Deep Audit

**Audit date:** 2026-08-25  
**Scope:** Current Student Workspace codebase only  
**Audit mode:** Static code tracing + focused test audit  
**Decision context:** Waiting indicator for the WRITE owner has been removed. Collaboration behavior itself is out of scope except where it directly affects Student Workspace write protection.

---

## 1. Executive Summary

Student Workspace already contains most of the major product capabilities expected for student management:

- Student list, search, filtering and bulk actions
- Student CRUD, archive, restore and delete
- Parent management
- Assessment
- Attendance history
- Financial summary
- Timeline
- Notes
- Documents
- Student reports
- Import/export
- Dashboard
- Analytics

The main problem is **not missing capability**. The current risk is that several capabilities are only partially completed, have inconsistent data semantics, or are not covered by focused tests.

### Overall assessment

| Area | Status |
|---|---|
| Core student CRUD | Strong |
| Student list | Strong |
| Parent management | Strong |
| Assessment | Strong |
| Timeline / notes / documents | Strong |
| Attendance history | Functional, read-oriented |
| Financial overview | Functional, needs business/UX boundary review |
| Reports | Functional but incomplete UX |
| Dashboard | Functional but contains data-semantic defects |
| Analytics | Partial / not production complete |
| Write-mode UX consistency | Partial |
| Student Workspace regression tests | Weak |

**Estimated capability completion:** 75–80%  
**Estimated production-readiness:** 60–70%

---

# 2. Current Architecture

## 2.1 Workspace navigation

Current shell:

```text
Student Workspace
├── Dashboard
├── Students
├── Analytics
└── Student Detail
    ├── Profile
    │   ├── Quick Actions
    │   ├── Profile
    │   ├── Summary
    │   ├── Parents
    │   ├── Assessment
    │   ├── Timeline
    │   ├── Notes
    │   └── Documents
    ├── Financial
    ├── Attendance
    └── Reports
```

The navigation model is generally sound. The current issue is not navigation structure but **information density and inconsistent completion between pages**.

---

# 3. Audit by User Flow

## FLOW 1 — Create Student

### Current path

```text
Student Workspace
→ Students
→ Add Student
→ StudentFormDialog
→ StudentService.create_student()
→ repository/database
→ Student list refresh
```

### Assessment

**Status: GOOD**

The backend service has validation, student-code generation and report-policy integration.

### Gap

The shell/list refreshes locally after dialog completion, but there is no focused Student Workspace regression test proving:

```text
Create
→ selected/list/dashboard refresh
→ data survives workspace navigation
```

### Priority

P1 test coverage.

---

## FLOW 2 — Edit Student

### Current path

```text
Student Detail/List
→ StudentFormDialog
→ StudentService.update_student()
→ local refresh
```

### Assessment

**Status: GOOD, but UX write-state propagation is incomplete**

`StudentDetailPage.set_write_enabled()` currently propagates write state only to:

- Quick actions
- Assessment
- Notes
- Documents

Parent actions, profile edit/photo actions and some other write affordances may remain visible/enabled and only fail later through `WriteGuard`.

This is safe from a business-rule perspective, but inconsistent UX.

### Required improvement

When not in WRITE mode:

```text
Hide/disable write actions
```

rather than:

```text
Allow click
→ show permission denied
```

### Priority

P1 UX consistency.

---

## FLOW 3 — Parent Management

### Current path

```text
Student Detail
→ Parents
→ Add/Edit/Delete
→ ParentService
→ Timeline/data refresh
```

### Assessment

**Status: GOOD**

The detail page uses `WriteGuard.require_write()` before mutations.

### Gap

The add/edit/delete buttons are not clearly governed by the workspace-wide write-enabled state. The protection is therefore reactive rather than proactive.

### Priority

P1.

---

## FLOW 4 — Assessment

### Current path

```text
Student Detail
→ Assessment
→ AssessmentService
→ Timeline/report policy
→ detail refresh
```

### Assessment

**Status: STRONG**

Assessment is integrated with report policy and timeline-style refresh.

### Gap

No dedicated end-to-end regression test for:

```text
Create assessment
→ Student Detail refresh
→ Dashboard attention state changes
→ Report policy path
```

### Priority

P1 test coverage.

---

## FLOW 5 — Attendance

### Current path

```text
Session/Class workflow
→ AttendanceService
→ Attendance records
→ Student Detail / Attendance tab
```

Student Workspace currently provides attendance history and attendance rate.

### Assessment

**Status: FUNCTIONAL**

The Student Workspace attendance tab is primarily a read-only history view.

### Important product decision

This is acceptable if attendance editing belongs to Class/Session Workspace. That boundary should be kept explicit.

### Gap

No navigation shortcut exists from a student attendance record back to the relevant class/session.

### Priority

P2 UX.

---

## FLOW 6 — Financial

### Current path

```text
Student Detail
→ Financial tab
→ IncomeService
→ OutstandingService
→ summary/payment history
→ Open Finance
```

### Assessment

**Status: FUNCTIONAL**

The current split is conceptually good:

```text
Student Detail
→ student-specific overview

Finance Workspace
→ operational finance management
```

### Gap

Needs a concrete UX review to ensure the tab does not duplicate finance management.

### Recommendation

Keep Student Detail financial tab read-oriented. Mutating financial operations should remain in Finance Workspace.

### Priority

P2 boundary/polish.

---

## FLOW 7 — Notes and Documents

### Current path

```text
Student Detail
→ Notes/Documents
→ StudentNoteService / StudentDocumentService
→ Timeline
→ refresh
```

### Assessment

**Status: GOOD**

The service layer supports CRUD for notes and upload/list/delete for documents.

### Gap

No focused tests verify UI refresh after mutation or document lifecycle.

### Priority

P1 test coverage.

---

## FLOW 8 — Reports

### Current path

```text
Student Detail
→ Reports
→ ReportListWidget
→ ReportService
→ open generated file
```

### Assessment

**Status: PARTIAL**

The list/open flow exists.

The workspace does not expose a clear direct flow for:

```text
Generate report now
```

The system currently relies heavily on report-policy/automatic generation.

### Product gap

A user working from Student Detail should have a clear answer to:

> “I want to generate a report for this student now.”

### Priority

P1.

---

## FLOW 9 — Import / Export

### Current path

```text
Students
→ Import Excel
→ StudentImportService

Students
→ Export
→ StudentExportService
```

### Assessment

**Status: GOOD**

Core capability exists.

### Gap

No visible audit was found for:

- duplicate student handling
- partial import failures
- import preview
- rollback/atomicity expectations

These may exist in implementation but are not represented by focused workspace tests.

### Priority

P2.

---

## FLOW 10 — Archive / Activate / Delete

### Current path

```text
Student List
→ Context/bulk action
→ archive/activate/delete
→ StudentService
→ refresh
```

### Assessment

**Status: FUNCTIONAL**

The service distinguishes archive, activate, soft delete and restore.

### Important semantic issue

Dashboard and Analytics do not consistently apply the same archived/deleted filters. This can make:

```text
Student List
```

and:

```text
Dashboard / Analytics
```

show contradictory totals.

### Priority

P0.

---

# 4. Confirmed Data-Semantic Defects

## DEFECT S-01 — Dashboard “Total Students” can include soft-deleted students

In `StudentDashboardService.get_stats()`:

```text
total = len(all_students)
```

where `all_students` comes from an including-deleted query.

But:

```text
active
archived
```

explicitly skip soft-deleted students.

Therefore the invariant:

```text
Total = Active + Archived
```

can be false.

### Example

```text
1 soft-deleted student
10 active
2 archived

Dashboard:
Total = 13
Active = 10
Archived = 2
```

### Required fix

Define dashboard semantics explicitly. Recommended:

```text
Total = Active + Archived
Soft-deleted = excluded from dashboard KPIs
```

**Priority: P0**

---

## DEFECT S-02 — “Parent Coverage” displays Assessment Completion Rate

`StudentDashboardService.QuickInsights` contains:

- `total_parents`
- `assessment_completion_rate`

But the dashboard UI labels one metric:

```text
Parent Coverage
```

while displaying:

```text
assessment_completion_rate
```

This is a direct semantic/UI defect.

### Required fix

Either:

```text
Parent Coverage
= students with at least one parent / active students
```

or change the label to:

```text
Assessment Coverage
```

**Priority: P0**

---

## DEFECT S-03 — Analytics counts include deleted/archived students

`StudentAnalyticsService` uses broad queries such as:

```text
session.query(Student).count()
session.query(Student).all()
```

The analytics service therefore does not apply the same active/archived/deleted semantics used elsewhere.

This can make analytics disagree with:

- Student List
- Dashboard
- Student Dashboard Service

### Required fix

Create one explicit student-population definition for analytics.

Recommended default:

```text
Analytics population
= deleted_at IS NULL
AND status != ARCHIVED
```

Archived analytics can be added later as an explicit filter.

**Priority: P0**

---

# 5. Dashboard Audit

## Current sections

- KPI cards
- Today's summary
- Quick insights
- Need attention
- Upcoming events
- Recent activities
- Quick actions

## Assessment

The dashboard is feature-rich, but it currently has too much breadth before data semantics are fully correct.

### Recommendation

Do not add more dashboard cards.

First complete:

1. KPI consistency
2. Parent coverage metric
3. Attention rules
4. Actionability of each section

### Actionability rule

Each dashboard section should answer:

```text
What should the user do next?
```

If a section is purely informational and duplicates Analytics, consider removing or reducing it.

---

# 6. Analytics Audit

## Current features

- Average score
- Total students
- Monthly growth
- Enrollment trend
- Assessment distribution
- Age distribution
- Score distribution

## Confirmed incomplete behavior

The button:

```text
Export Analytics Report
```

currently shows:

```text
Analytics report export will be available soon.
```

This is a visible incomplete feature.

### Required decision

Either:

A. implement export, or  
B. remove/disable the button until implemented.

Leaving a production button that only says “coming soon” is not recommended for the current product.

### Priority

P1.

---

# 7. Student Detail Audit

## Strength

The detail page is a useful student-centric workspace.

## Risk

`StudentDetailPage` currently orchestrates many services:

- Student
- Parent
- Timeline
- Assessment
- Summary
- Session
- Session Note
- Highlight
- Student Note
- Document
- Income
- Class
- Permission
- Outstanding
- Attendance
- Report
- Platform context
- Collaboration

This is a large dependency surface.

### Recommendation

Do not perform a broad refactor now.

First finish product flows.

Later, split orchestration by tab:

```text
StudentDetailCoordinator
├── ProfileTabController
├── FinancialTabController
├── AttendanceTabController
└── ReportsTabController
```

### Priority

P3 architectural cleanup.

---

# 8. Write-Mode UX Audit

Business protection is generally present through:

```text
WriteGuard
CollaborationManager.ensure_write()
```

However UI behavior is inconsistent.

Some actions:

```text
disabled when no WRITE
```

Others:

```text
remain clickable
→ WriteGuard rejects
```

This creates a mixed experience.

## Target rule

When user does not have WRITE:

```text
READ-ONLY MODE
```

should be visible and all mutation affordances should be consistently disabled.

Read-only actions remain enabled:

- Search
- Filter
- Export
- View report
- View attendance
- View financial summary
- Navigate

Mutation actions disabled:

- Add/Edit/Delete student
- Archive/Activate
- Parent mutations
- Assessment mutations
- Note mutations
- Document upload/delete
- Profile photo change
- Import

**Priority: P1**

---

# 9. Test Audit

## Current focused tests found

- `test_student_service.py`
- `test_student_ui_helpers.py`
- `test_student_highlight_service.py`

There are no dedicated test files for:

- Student Workspace shell
- Dashboard
- Student Detail
- Parent UI flow
- Attendance widget
- Financial widget
- Reports widget
- Analytics page

## Focused test execution during audit

The audit environment could not complete the focused suite because:

1. `PySide6` is not installed in the audit runtime.
2. `HighlightTimelineHandler` has a `NameError: Event is not defined` during collection.

Therefore:

> This audit does not claim the Student test suite is green.

The `HighlightTimelineHandler` collection error is outside Student Workspace UI but is relevant to the student's test ecosystem.

---

# 10. Recommended Completion Roadmap

## SPRINT STUDENT-1 — Data Correctness and Completion

### P0

1. Fix dashboard total semantics.
2. Fix Parent Coverage metric.
3. Normalize active/archived/deleted population rules across:
   - Student List
   - Dashboard
   - Analytics
4. Add regression tests for these semantics.

### P1

5. Make Student Detail write-mode UI consistently read-only.
6. Add direct “Generate Report” flow or remove incomplete report expectation.
7. Remove or implement Analytics export placeholder.
8. Add tests for:
   - Student create/edit/archive
   - Parent mutation
   - Assessment mutation
   - Student detail refresh

---

## SPRINT STUDENT-2 — User Flow Polish

1. Attendance navigation to class/session.
2. Review Financial tab vs Finance Workspace boundary.
3. Improve import failure/duplicate feedback.
4. Review Dashboard actionability.
5. Standardize UI language.

---

## SPRINT STUDENT-3 — Regression Safety

Add focused integration tests for:

```text
Create Student
→ Dashboard/List update

Edit Student
→ Detail/List refresh

Archive Student
→ Dashboard/Analytics/List semantics

Add Parent
→ Detail + dashboard attention refresh

Assessment
→ Detail + report policy

Attendance
→ Student history

Generate Report
→ Report list + open file
```

---

# 11. Recommended Next Implementation

The recommended next task is:

```text
STUDENT-1.1 — Student Population & Dashboard Correctness
```

Scope:

1. Define one population rule:
   - active
   - archived
   - soft-deleted
2. Apply it consistently to Dashboard and Analytics.
3. Fix Parent Coverage.
4. Add regression tests.

This is the safest next step because it fixes real correctness defects without changing the established Student Workspace architecture.
