# TASK-011 - Session Detail: Attendance Tab

Version: 1.0

Priority: 🔴 CRITICAL

Estimated Time: 4~6 Days

Owner: DeepSeek

Status: READY

---

# Background

The Academic Domain has been finalized.

Architecture Freeze

Class
    │
    ▼
Session (Academic Aggregate Root)
    ├── Attendance
    ├── Assessment
    ├── Homework
    ├── SessionNote
    ├── Lesson Resources
    └── Student Highlight

Session is now the single source of truth
for all academic activities.

Attendance must be implemented
inside Session.

Attendance is NOT a standalone module.

---

# Objective

Enhance Session Detail.

Implement Attendance as the first
Session feature.

Teachers should complete attendance
while viewing a Session.

No Attendance Workspace is allowed.

---

# Scope

Included

✅ Session Detail

✅ Attendance Tab

✅ Attendance Status

✅ Attendance Summary

✅ Batch Attendance

✅ Timeline Integration

---

Not Included

❌ Assessment

❌ Homework

❌ Resources

❌ Parent Portal

❌ Reports

---

# Business Workflow

Teacher

↓

Class

↓

Session

↓

Attendance Tab

↓

Take Attendance

↓

Save

Student never creates attendance.

Attendance belongs to Session.

---

# Session Detail Layout

Session Detail

------------------------------------------------

Session Information

Topic

Teacher

Date

Time

Status

------------------------------------------------

Tabs

Attendance

Assessment (Coming Soon)

Homework (Coming Soon)

Notes

Resources

------------------------------------------------

Attendance is the default tab.

---

# Attendance Status

Present

Late

Absent

Excused

Only these four statuses
are allowed.

---

# Attendance List

Display

Student Name

Attendance Status

Arrival Time (optional)

Teacher Comment

Display all enrolled students
for the class.

---

# Teacher Actions

Teacher can

Mark Present

Mark Late

Mark Absent

Mark Excused

Edit Comment

Save

---

# Batch Attendance

Provide

Select All

↓

Present

Teacher only changes exceptions.

This is expected to be
the most common workflow.

---

# Attendance Summary

Display

Present

Late

Absent

Excused

Attendance Rate

Summary must be calculated.

Never stored.

---

# Student Relationship

Attendance

↓

Student

↓

Enrollment

↓

Class

↓

Session

Attendance never belongs directly
to Student.

---

# Backend

Implement

AttendanceService

AttendanceRepository

AttendanceDTO

Business rules belong
to AttendanceService.

Repository handles persistence only.

---

# Timeline

Reuse TimelineService.

Events

Attendance Created

Attendance Updated

Do NOT create
AttendanceTimelineService.

---

# Permission

attendance.view

attendance.create

attendance.update

Reuse RBAC.

Teachers

Create

Update

Admins

Full Access

Reception

Read Only

---

# Frontend

Reuse

Session Detail

Existing Table

Existing Badge

Existing Dialog

Existing Timeline

No redesign.

Attendance must appear
as a Session tab.

---

# Deliverables

Attendance Tab

Attendance CRUD

Attendance Summary

Batch Attendance

Timeline Integration

Permission Integration

Testing

---

# Acceptance Criteria

✔ Session Detail contains Attendance tab.

✔ Teacher can take attendance.

✔ Batch attendance works.

✔ Attendance Summary is correct.

✔ Timeline updated.

✔ Permissions enforced.

✔ Build passes.

---

# Technical Rules

Attendance belongs to Session.

Attendance never belongs directly
to Class.

Attendance never belongs directly
to Student.

No duplicated business logic.

Reuse existing architecture.

---

# UI Principles

Teachers work inside Session.

Teachers never leave Session
to perform attendance.

Attendance is contextual.

The UI should support
real classroom workflow.

---

# Future Compatibility

The Attendance Tab must be designed
to coexist with future tabs.

Assessment

Homework

Resources

Notes

All tabs should follow
the same interaction pattern.

No redesign should be required
when future tabs are added.

---

# Regression Testing

Verify

Session Detail

Attendance CRUD

Timeline

Permission

Session Navigation

Student View

Build

---

# Definition of Done

Attendance is complete when

Teachers can complete attendance
without leaving Session.

Attendance data belongs to Session.

Session becomes the true operational
workspace for teachers.

No additional Attendance Workspace
exists anywhere in the system.

---

# Architecture Reminder

Academic Domain

Student
        │
Enrollment
        │
Class
        │
Session
        ├── Attendance
        ├── Assessment
        ├── Homework
        ├── Notes
        ├── Resources
        └── Timeline

Session is permanently frozen
as the Academic Aggregate Root.

No future academic feature
may bypass Session.