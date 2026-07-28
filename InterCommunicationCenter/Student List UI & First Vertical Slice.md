# CenterManager — Sprint 0.4 Developer Contract

**Sprint:** 0.4
**Name:** Student List UI & First Vertical Slice
**Developer:** DeepSeek
**Technical Lead / Reviewer:** ChatGPT
**Product Owner:** An
**Status:** READY FOR DEVELOPMENT

---

# 1. Sprint Objective

Build the first usable desktop workflow of CenterManager.

At the end of this sprint:

```text
Launch CenterManager
        ↓
Student List
        ↓
+ Add Student
        ↓
Student Form
        ↓
Save
        ↓
StudentService
        ↓
StudentRepository
        ↓
SQLite
        ↓
Refresh Student List
```

Also support:

```text
Student List
      ↓
Double Click Student
      ↓
Basic Student Profile
```

This is the first complete vertical slice of the application.

---

# 2. Frozen Architecture

The following foundations are FROZEN:

```text
Foundation              v0.1
Database Foundation     v0.2
Student Core Service    v0.3
```

Do NOT redesign them.

Required architecture:

```text
PySide6 UI
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

Forbidden:

```text
UI → Repository        ❌
UI → SQLAlchemy        ❌
UI → SQLite            ❌
```

UI must use `StudentService`.

---

# 3. UI Technology

Continue using:

```text
Python
PySide6
```

Do NOT introduce:

```text
Tkinter
PyQt
Web UI
Flask
Django
Electron
QML
```

in this sprint.

Use Qt Widgets.

---

# 4. UX Philosophy

CenterManager is an internal management tool.

UI priorities:

```text
1. Easy to understand
2. Fast to operate
3. Low visual clutter
4. Important information visible immediately
5. Long information belongs in profile, not list
```

Do NOT attempt a flashy dashboard.

Do NOT over-design.

Aim for:

```text
clean
professional
simple
desktop-management style
```

---

# 5. Main Window

Implement/update:

```text
src/centermanager/ui/main_window.py
```

Main window should conceptually contain:

```text
┌─────────────────────────────────────────────┐
│ CenterManager                              │
├────────────┬────────────────────────────────┤
│            │                                │
│ Students   │        Page Content            │
│            │                                │
│            │                                │
│            │                                │
│            │                                │
├────────────┴────────────────────────────────┤
│ Status                                     │
└─────────────────────────────────────────────┘
```

V1 sidebar only needs:

```text
Students
```

Do NOT add fake/non-functional:

```text
Dashboard
Classes
Teachers
Payments
Reports
Settings
```

just for appearance.

Future navigation may be added later.

---

# 6. Default Page

Application starts on:

```text
Students
```

page.

No dashboard required.

---

# 7. Student List Page

Create conceptually:

```text
ui/
└── students/
    ├── student_list_page.py
    ├── student_form_dialog.py
    └── student_profile_dialog.py
```

Exact naming may differ slightly if justified.

Do not place all UI logic inside `main_window.py`.

---

# 8. Student List Layout

Target:

```text
Students

[ Search... ]                         [+ Add Student]

────────────────────────────────────────────────────────

Code      Name              Age      Level          Status
HS001     Nguyễn Văn A      11       Python Basic   ACTIVE
HS002     Trần Minh B       13       Robotics L1    ACTIVE
HS003     Lê Gia C          10       Scratch        ACTIVE
```

Columns required:

```text
Student Code
Full Name
Age
Current Level
Status
```

Do NOT display:

```text
Parent
Notes
Assessment
Products
Timeline
Attachments
```

in the list.

Those belong to profile.

---

# 9. Student List Data Source

List MUST use:

```text
StudentService.list_students()
```

Do not query database directly.

Conceptually:

```text
StudentListPage
       ↓
StudentService.list_students()
       ↓
Student[]
       ↓
Table
```

---

# 10. Student Table

Use an appropriate Qt table widget/model.

For ~100–500 students, either:

```text
QTableWidget
```

or:

```text
QTableView + simple model
```

is acceptable.

Do NOT build a complex generic table framework.

The developer should favor simplicity.

---

# 11. Table Behavior

Requirements:

* Row selection.
* Select full row.
* Single selection.
* Read-only cells.
* Reasonable column resizing.
* Student code visible.
* Name should receive useful width.
* Double-click row opens profile.

Users must NOT directly edit database values inside table cells.

---

# 12. Age Calculation

Database stores:

```text
date_of_birth
```

UI displays:

```text
Age
```

Age is derived data.

Do NOT store age in database.

Calculate based on current date.

Correct behavior must account for whether birthday has occurred this year.

Example conceptually:

```text
DOB: 2015-10-20
Today: 2026-07-27

Age = 10
```

If DOB is unknown:

```text
-
```

or blank is acceptable.

Create a small reusable helper if appropriate.

---

# 13. Add Student Button

Provide:

```text
+ Add Student
```

Click:

```text
StudentListPage
      ↓
StudentFormDialog
```

Student Code must NOT be manually entered.

It is generated by `StudentService`.

---

# 14. Add Student Form

Minimum fields:

```text
Full Name *
Preferred Name
Date of Birth
Gender
Current Level
Notes
```

Status may either:

* default silently to ACTIVE, or
* appear as ACTIVE in the form.

For V1, defaulting silently to ACTIVE is preferred.

Do not expose Student Code input.

---

# 15. Full Name

Required field.

UI should visually indicate requirement:

```text
Full Name *
```

Do not rely exclusively on UI validation.

Final validation still comes from:

```text
StudentService
```

---

# 16. Date of Birth

Use an appropriate Qt date input.

Important:

`date_of_birth` is nullable.

The UI MUST support:

```text
No date of birth
```

Do not force a fake date.

If `QDateEdit` is used, implement a clear/nullable strategy.

Do not save:

```text
2000-01-01
```

or today's date merely because the user left the field empty.

---

# 17. Gender

Use a simple input.

Acceptable:

```text
QComboBox
```

with values such as:

```text
Not specified
Male
Female
Other
```

Map:

```text
Not specified → None
```

Do not introduce DB enum.

---

# 18. Current Level

Simple text input is acceptable for V1.

Example:

```text
Scratch Basic
Python Beginner
Robotics L1
```

Do NOT build course/level management.

---

# 19. Notes

Use:

```text
QPlainTextEdit
```

or equivalent multi-line widget.

This field exists specifically because student information may be long.

Do not constrain it to a single-line input.

---

# 20. Save Student

When user clicks:

```text
Save
```

UI must call:

```text
StudentService.create_student(...)
```

On success:

```text
Create
  ↓
Service commit
  ↓
Dialog closes
  ↓
Student list refreshes
  ↓
New Student visible
```

No application restart should be required.

---

# 21. Validation Error UX

Catch business-level exceptions such as:

```text
StudentValidationError
```

and display a user-friendly Qt message.

Example:

```text
Please enter the student's full name.
```

Do NOT show:

```text
Traceback
IntegrityError
SQLAlchemy exception
```

to the user.

Unexpected exceptions may be logged and shown as a generic failure message.

---

# 22. Cancel

Form must have:

```text
Save
Cancel
```

Cancel:

```text
closes dialog
does not save anything
does not refresh unnecessarily
```

---

# 23. Student List Refresh

Implement an explicit method conceptually:

```text
refresh_students()
```

Used:

```text
page opened
after successful student creation
after future student update
```

Keep refresh logic centralized.

---

# 24. Empty State

If no students exist:

Do not crash.

Table may simply be empty.

Preferred additional text:

```text
No students yet.
Add the first student to get started.
```

is acceptable but not mandatory.

Do not spend excessive effort on empty-state design.

---

# 25. Search — V1 Local Filter

The Search box is included in this sprint, but DO NOT add database search architecture yet.

For current scale:

```text
StudentService.list_students()
        ↓
UI receives ~100 students
        ↓
local filtering
```

Filter at minimum by:

```text
student_code
full_name
```

Case-insensitive.

Examples:

```text
Search: HS01
Search: Nguyễn
Search: an
```

No fuzzy search required.

No SQL LIKE query required.

No pagination.

---

# 26. Search Behavior

Filtering should occur as the user types.

Conceptually:

```text
search text changed
      ↓
filter current Student list
      ↓
update visible rows
```

Do NOT call database on every keystroke.

---

# 27. Basic Student Profile

Double-clicking a student opens:

```text
StudentProfileDialog
```

This is NOT the final Student Profile.

Only implement a basic read-only profile in Sprint 0.4.

---

# 28. Basic Profile Content

Display:

```text
Student Code
Full Name
Preferred Name
Date of Birth
Age
Gender
Current Level
Status
Notes
```

Example:

```text
HS023

NGUYỄN VĂN A

Preferred name:
An

Date of birth:
12/08/2015

Age:
10

Current level:
Python Beginner

Status:
ACTIVE

Notes:
Student learns quickly...
```

Do NOT show placeholder sections for unimplemented domains.

No fake:

```text
Assessments — Coming Soon
Products — Coming Soon
Parents — Coming Soon
```

Keep profile clean.

---

# 29. Profile Data

When opening profile, use:

```text
StudentService.get_student(student_id)
```

Do not assume table data is authoritative.

Flow:

```text
Double click
    ↓
student_id
    ↓
StudentService.get_student()
    ↓
Profile
```

This ensures profile loads current persisted data.

---

# 30. Profile Editing

DO NOT implement profile editing in Sprint 0.4.

Profile is read-only.

Edit will be introduced in a later vertical slice.

Do not add disabled Edit buttons.

---

# 31. Delete / Restore

DO NOT expose:

```text
Delete
Restore
```

in UI yet.

Backend support exists, but destructive UX needs separate design.

---

# 32. Window Behavior

Dialogs should:

* have sensible initial size,
* be resizable where useful,
* remain usable on normal laptop displays,
* not require maximized screen.

Do not hardcode giant fixed dimensions.

---

# 33. UI Styling

A small application stylesheet is allowed.

Keep it minimal.

Allowed:

```text
spacing
padding
font hierarchy
button sizing
table readability
```

Do NOT spend sprint time building:

```text
theme engine
dark mode
custom animation
custom widget library
icon framework
```

Default Qt appearance with modest polish is acceptable.

---

# 34. No Business Logic Duplication

UI may perform presentation helpers such as:

```text
age calculation
date formatting
display "-"
```

UI must NOT duplicate:

```text
Student Code generation
soft delete policy
database validation
transaction management
```

Those remain Service responsibilities.

---

# 35. Application Bootstrap

Application startup must initialize dependencies cleanly.

Conceptually:

```text
main
 ↓
create StudentService
 ↓
create MainWindow
 ↓
inject service
 ↓
show
```

Do not create random `StudentService()` instances throughout widgets if a clean dependency can be passed down.

Prefer:

```text
MainWindow(student_service)
        ↓
StudentListPage(student_service)
        ↓
StudentFormDialog(student_service)
```

Keep it simple; no DI framework.

---

# 36. Database Startup

The application must work against the configured production:

```text
runtime/Database/center.db
```

using the existing path/database infrastructure.

Do NOT hardcode database paths in UI.

Do NOT automatically destroy/recreate DB.

Do NOT call:

```text
Base.metadata.drop_all()
```

or similar.

---

# 37. Migration Responsibility

Do NOT redesign migration startup in this sprint.

If current application startup already has an approved database initialization path, preserve it.

If application cannot start because production DB lacks the current schema, document the issue rather than introducing an unreviewed migration framework inside UI code.

---

# 38. UI Error Boundary

Unexpected UI-triggered operation errors should not terminate the application.

For create/profile-load operations:

```text
Service exception
      ↓
UI handles
      ↓
MessageBox
      ↓
Application continues
```

Use specific business messages where possible.

Generic unexpected error message is acceptable for unknown errors.

---

# 39. Required UI Tests

Do not attempt pixel-perfect GUI tests.

Add focused tests for logic that matters.

At minimum cover:

```text
age calculation
student filtering
student row mapping/display helper
nullable DOB conversion if helper exists
```

Where practical, test UI interaction using PySide6 widgets.

---

# 40. Student List Integration Test

Add at least one integration-style UI test:

```text
temporary DB
    ↓
StudentService
    ↓
create HS001
create HS002
    ↓
StudentListPage
    ↓
refresh_students()
    ↓
2 visible rows
```

No production database.

---

# 41. Add Student Integration Test

Add at least one test proving:

```text
StudentFormDialog
       ↓
valid input
       ↓
StudentService
       ↓
student persisted
```

The test does not need to test every Qt visual detail.

Focus on the vertical slice.

---

# 42. Search Test

Create students such as:

```text
HS001 Nguyễn Văn An
HS002 Trần Minh Bình
```

Verify:

```text
"HS001"
```

shows first student.

Verify:

```text
"Bình"
```

shows second student.

Verify case-insensitive matching.

---

# 43. Profile Test

Verify:

```text
double-click/open profile
```

or directly instantiate profile with student ID and service.

Profile must load Student using:

```text
StudentService.get_student()
```

and display expected core fields.

Avoid fragile coordinate-based GUI testing.

---

# 44. Production DB Safety

Automated UI tests MUST use isolated temporary databases.

Running:

```text
pytest
```

must not create, modify or delete production:

```text
runtime/Database/center.db
```

Existing production safety requirements remain mandatory.

---

# 45. Manual Acceptance Test

Developer must manually verify this exact workflow:

```text
1. Start CenterManager

2. Student List opens

3. Click + Add Student

4. Enter:
   Full Name = Nguyễn Văn An
   Preferred Name = An
   Current Level = Python Beginner

5. Save

6. Student appears in list

7. Student Code generated automatically

8. Search "An"

9. Student remains visible

10. Clear search

11. Double-click student

12. Basic profile opens

13. Profile information matches saved data

14. Close application

15. Reopen application

16. Student is still present
```

This manual test is mandatory because this is the first user-visible vertical slice.

---

# 46. Explicit Non-Goals

DO NOT implement:

```text
Edit Student
Delete Student UI
Restore Student UI

Parent UI
Enrollment UI
Assessment UI
Timeline UI
Product UI
Progress UI
Attachment UI

PDF
Excel
Google Drive

Dashboard
Class Management
Teacher Management
Course Management
Payment

Authentication
Admin Login
Permissions

Advanced Search
Database Search
Pagination

Themes
Dark Mode
Animations
```

---

# 47. Suggested File Structure

Target approximately:

```text
src/centermanager/ui/
│
├── main_window.py
│
├── styles.py                  optional
│
└── students/
    ├── __init__.py
    ├── student_list_page.py
    ├── student_form_dialog.py
    ├── student_profile_dialog.py
    └── helpers.py             optional
```

Tests:

```text
tests/
├── test_student_ui_helpers.py
└── test_student_ui.py
```

Exact split may vary if justified.

Avoid unnecessary files/classes.

---

# 48. Acceptance Criteria

**AC-01** Existing backend tests PASS.

**AC-02** Application launches successfully.

**AC-03** Students page is the default page.

**AC-04** Student list uses `StudentService.list_students()`.

**AC-05** Table displays Code, Name, Age, Level, Status.

**AC-06** Age is calculated, not stored.

**AC-07** `+ Add Student` opens form.

**AC-08** Student Code is not editable/input by user.

**AC-09** Full Name is required.

**AC-10** DOB supports NULL.

**AC-11** Notes supports multiline text.

**AC-12** Save calls `StudentService.create_student()`.

**AC-13** Successful save refreshes list immediately.

**AC-14** Cancel creates no Student.

**AC-15** Business validation errors are user-friendly.

**AC-16** UI does not expose SQLAlchemy/database exceptions.

**AC-17** Search filters Code and Full Name locally.

**AC-18** Search is case-insensitive.

**AC-19** Search does not query DB per keystroke.

**AC-20** Double-click opens Basic Student Profile.

**AC-21** Profile reloads Student via StudentService.

**AC-22** Profile is read-only.

**AC-23** UI never accesses Repository/SQLAlchemy/SQLite directly.

**AC-24** StudentService dependency is passed cleanly into UI.

**AC-25** UI tests use isolated DB.

**AC-26** Production DB is untouched by tests.

**AC-27** Add Student vertical-slice test PASS.

**AC-28** Student List integration test PASS.

**AC-29** Search test PASS.

**AC-30** Profile test PASS.

**AC-31** Manual create → close → reopen persistence workflow PASS.

**AC-32** No out-of-scope feature implementation.

**AC-33** Full `pytest` PASS.

---

# 49. Required Completion Report

Return:

## 1. Summary

## 2. Files Created

## 3. Files Modified

## 4. UI Structure

Explain:

```text
MainWindow
StudentListPage
StudentFormDialog
StudentProfileDialog
```

## 5. Dependency Flow

Show how StudentService reaches UI components.

## 6. Student List

Describe columns and refresh behavior.

## 7. Add Student Flow

Describe:

```text
UI → Service → DB → refresh
```

## 8. Search

Explain local filtering implementation.

## 9. Profile

Explain profile loading behavior.

## 10. Nullable DOB Handling

Explain exactly how empty DOB is represented and passed as `None`.

## 11. Error Handling

Explain business vs unexpected errors.

## 12. Automated Test Result

Provide actual:

```text
pytest
```

result.

## 13. Manual Acceptance Result

Report each of the 16 manual steps as PASS/FAIL.

## 14. Production DB Safety

Confirm automated tests do not modify production DB.

## 15. Deviations

If none:

```text
None.
```

## 16. Known Issues

If none:

```text
None.
```

## 17. Acceptance Checklist

```text
AC-01 PASS
...
AC-33 PASS
```

---

# 50. Review Gate

After completion:

```text
DeepSeek
   ↓
Source Package
   +
Completion Report
   ↓
Technical Lead Review
```

Do NOT begin the next UI sprint.

Technical Lead will independently review:

```text
UI → Service boundary
dependency injection
nullable DOB
local search
age calculation
error handling
database isolation
vertical-slice persistence
UI structure
scope discipline
```

Only after:

```text
SPRINT 0.4 PASS
```

will the next Student Profile functionality be designed.

---

# END OF SPRINT 0.4 CONTRACT
