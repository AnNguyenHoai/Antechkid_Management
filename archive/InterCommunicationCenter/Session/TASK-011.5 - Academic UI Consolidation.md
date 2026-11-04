# TASK-011.5 - Academic UI Consolidation (Single Write Attendance)

Version: 1.0

Priority: 🔴 HIGH

Estimated Time: 1~2 Days

Owner: DeepSeek

Status: READY

---

# Background

The Academic Domain architecture has been finalized.

Backend Architecture

Class
    │
    ▼
Session (Academic Aggregate Root)
    ├── Attendance
    ├── Assessment
    ├── Homework
    ├── Notes
    └── Resources

Current implementation contains Attendance in two UI locations:

1. Class Workspace
2. Teaching Workspace (Session)

This duplicates the same business action.

The project follows the same architectural principle already used in Finance:

Single Write
Multiple Read

Attendance must follow this rule.

---

# Objective

Consolidate Attendance into a single operational workspace.

Attendance editing must exist ONLY inside Teaching Workspace.

All other screens become read-only consumers.

---

# Final UI Architecture

Class Workspace

Overview

↓

Weekly Sessions

↓

Open Session

↓

Teaching Workspace

    Attendance
    Overview

Attendance is removed completely
from Class Workspace.

---

# Scope

Included

✅ Remove Class Attendance

✅ Update Navigation

✅ Update Read Sources

✅ Cleanup obsolete code

✅ Regression Test

---

Not Included

❌ Assessment

❌ Homework

❌ Resources

❌ Reports

---

# STEP 1

Remove Attendance Tab

Delete

Class Detail

↓

Attendance Tab

All related menu items

Navigation

Toolbar buttons

Context menus

No Attendance editing
may remain in Class Workspace.

---

# STEP 2

Teaching Workspace

Teaching Workspace becomes

the ONLY Attendance editor.

Attendance workflow

Teacher

↓

Open Session

↓

Attendance

↓

Save

Only this workflow is valid.

---

# STEP 3

Read Flow Review

Review every screen
that displays Attendance.

Examples

Student Workspace

Student Financial Summary

Dashboard

Reports

Statistics

Future Parent Portal

Future Analytics

All must READ

AttendanceService

No duplicated query logic.

---

# STEP 4

Navigation Review

Class Workspace

Overview

↓

View Session

↓

Teaching Workspace

No direct

Attendance entry

should remain.

---

# STEP 5

Overview Enhancement

Teaching Workspace

Overview

must become

Session Summary.

Display

Session Number

Topic

Teacher

Date

Time

Status

Assessment Summary

Homework Summary

Teacher Notes

Do NOT duplicate Attendance here.

Instead display

Attendance Summary

Example

Present 18

Late 1

Absent 2

Attendance Rate 90%

Overview is read-only.

Attendance editing belongs only
to Attendance tab.

---

# STEP 6

Student Workspace

Student Attendance

must continue working.

However

Student Workspace

must never own Attendance.

It reads Attendance data

through AttendanceService.

No local Attendance state.

---

# STEP 7

Dashboard

Dashboard Attendance

must read

AttendanceService.

Never calculate independently.

---

# STEP 8

Cleanup

Remove

Unused routes

Unused actions

Unused dialogs

Unused ViewModels

Unused widgets

Unused commands

related to

Class Attendance.

Search entire project

Attendance

to ensure

there is only one write path.

---

# Architecture Rule

Single Write

Teaching Workspace

↓

Attendance

Multiple Read

Student

Dashboard

Reports

Analytics

Parent Portal

All read

AttendanceService.

---

# Acceptance Criteria

✔ Class Workspace no longer contains Attendance.

✔ Teaching Workspace is the only Attendance editor.

✔ Student Attendance still works.

✔ Dashboard still works.

✔ Attendance Summary visible in Session Overview.

✔ Navigation updated.

✔ No duplicated Attendance logic.

✔ Regression test passed.

---

# Regression Checklist

Create Attendance

Edit Attendance

Read Attendance

Student Attendance

Attendance Summary

Dashboard

Timeline

Permissions

Build

---

# Deliverables

Updated Navigation

Attendance Consolidation

Overview Enhancement

Cleanup Report

Regression Report

Architecture Update

---

# Definition of Done

Attendance editing exists
in exactly one place.

Teaching Workspace.

All other modules

read Attendance

from the same source.

The Academic Domain now follows
the same architectural principle
as Finance:

Single Write

Multiple Read

No duplicated business workflow.