# CENTER DESIGN SYSTEM

# 00. INFORMATION ARCHITECTURE

Version: 1.0

Status: Approved

---

# Purpose

This document defines the overall structure of CenterManager.

Information Architecture (IA) determines

- what modules exist,
- how they relate,
- where users navigate,
- and where information belongs.

A clear IA reduces navigation complexity
and keeps future expansion predictable.

---

# Design Principles

The system should answer three questions
within five seconds.

1. Where am I?
2. What can I do here?
3. Where should I go next?

Every page should have one clear purpose.

---

# Product Structure

CenterManager

├── Dashboard
├── Students
├── Teachers
├── Courses
├── Classes
├── Attendance
├── Assessments
├── Finance
├── Reports
└── Settings

Each module is responsible
for one business domain.

Modules should not overlap.

---

# Dashboard

Purpose

Provide an operational overview.

Contains

Today's Summary

Need Attention

Upcoming Events

Recent Activities

Quick Insights

Dashboard should never become
a management page.

No CRUD operations.

---

# Students Module

Purpose

Manage student lifecycle.

Pages

Student Dashboard

↓

Student List

↓

Student Detail

↓

Student Analytics

Responsibilities

Student Profile

Enrollment

Attendance

Assessment

Parents

Documents

Timeline

---

# Teachers Module

Purpose

Manage teachers.

Pages

Teacher Dashboard

↓

Teacher List

↓

Teacher Detail

↓

Teacher Analytics

Responsibilities

Teacher Profile

Assigned Classes

Schedule

Performance

Timeline

---

# Courses Module

Purpose

Manage learning programs.

Pages

Course List

↓

Course Detail

↓

Course Analytics

Responsibilities

Course Information

Curriculum

Duration

Teachers

Classes

Enrollment Statistics

---

# Classes Module

Purpose

Manage actual teaching classes.

Pages

Class Dashboard

↓

Class List

↓

Class Detail

Responsibilities

Schedule

Students

Teacher

Room

Attendance

Lesson History

---

# Attendance Module

Purpose

Manage attendance records.

Pages

Attendance Dashboard

↓

Attendance List

↓

Attendance Analytics

Responsibilities

Daily Attendance

Absence

Late Arrival

Attendance Trends

---

# Assessments Module

Purpose

Manage student evaluations.

Pages

Assessment Dashboard

↓

Assessment List

↓

Assessment Detail

↓

Analytics

Responsibilities

Scores

Comments

Teacher Feedback

Progress

History

---

# Finance Module

Purpose

Manage financial operations.

Pages

Finance Dashboard

↓

Invoices

↓

Payments

↓

Revenue Analytics

Responsibilities

Invoices

Payments

Outstanding Fees

Revenue

Expenses

---

# Reports Module

Purpose

Generate business reports.

Categories

Students

Teachers

Finance

Attendance

Assessments

Reports should be read-only.

---

# Settings Module

Purpose

Configure system behavior.

Categories

Organization

Users

Permissions

Academic Settings

Finance Settings

Notification Settings

Backup

System

---

# Navigation Rules

Navigation has three levels only.

Level 1

Main Module

Example

Students

Level 2

Workspace

Student List

Student Dashboard

Student Analytics

Level 3

Entity

Student Detail

Avoid deeper navigation.

---

# Cross Navigation

Modules should connect naturally.

Student Detail

↓

Assessment

↓

Attendance

↓

Invoice

↓

Timeline

Without returning to Dashboard.

---

# Global Search

Global Search should access

Students

Teachers

Courses

Classes

Invoices

Documents

Search should be available
from every page.

---

# Notifications

Notifications are global.

Examples

New Student

Payment Received

Assessment Completed

Upcoming Class

Notifications should always
link back to the related entity.

---

# Timeline

Every major business event
creates a timeline entry.

Timeline is the history
of the organization.

Examples

Student Created

Attendance Recorded

Assessment Completed

Invoice Paid

Parent Updated

---

# Future Expansion

New modules

must follow the same structure.

Dashboard

↓

List

↓

Detail

↓

Analytics

No custom navigation structures.

---

# Information Ownership

Each business entity
has one owner.

Student information

belongs to Students.

Payment information

belongs to Finance.

Assessment information

belongs to Assessments.

Avoid duplicated ownership.

---

# Final Principle

Information should exist
in exactly one place.

Other modules may reference it,

but should never duplicate it.

A simple architecture
is easier to learn,
easier to maintain,
and easier to extend.