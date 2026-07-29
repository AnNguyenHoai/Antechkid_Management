# WORKSPACE_SPEC.md

Version: 2.0

Status: APPROVED

Architecture Level: Product

Depends On

- ARCHITECTURE_V2.md
- NAVIGATION.md

---

# 1. Purpose

This document defines the standard structure of every Workspace inside CenterManager.

All existing and future Workspaces must follow this specification.

The goal is to ensure consistency across the entire product.

---

# 2. Workspace Philosophy

A Workspace represents one independent business domain.

A Workspace should feel like a self-contained application.

Users should never feel they are moving between unrelated systems.

Every Workspace follows the same structure.

---

# 3. Workspace Standard Structure

Every Workspace consists of six layers.

```
Workspace

│

├── Dashboard

│

├── Business List

│

├── Business Detail

│

├── Workspace Screen

│

├── Reports

│

└── Settings (optional)
```

---

# 4. Dashboard

Purpose

Provide an overview of the current Workspace.

Dashboard should answer

"What should I do?"

Dashboard should NEVER become a working screen.

Dashboard may contain

- Statistics
- Pending Tasks
- Recent Activities
- Shortcuts
- Notifications

Dashboard should not contain CRUD operations.

---

# 5. Business List

Purpose

Display business objects.

Examples

Teacher Workspace

```
Courses

Classes

Sessions
```

Student Workspace

```
Students
```

Finance Workspace

```
Invoices

Payments
```

Business List is responsible for

- Search
- Filter
- Sort
- Pagination
- Selection

Business List does not perform business operations.

---

# 6. Business Detail

Purpose

Display information of one business object.

Example

Student Detail

Course Detail

Invoice Detail

Employee Detail

Business Detail contains

Overview

Related Information

History

Metadata

Business Detail is information-oriented.

---

# 7. Workspace Screen

Workspace Screen is where users perform actual work.

Examples

Teaching Workspace

Assessment Workspace

Invoice Workspace

Payroll Workspace

Workspace Screen should focus on completing tasks.

Workspace Screen owns business operations.

---

# 8. Reports

Reports belong to the current Workspace.

Example

Teacher Workspace

Attendance Report

Teaching Hours

Session Statistics

Student Workspace

Learning Progress

Assessment Summary

Finance Workspace

Revenue

Expense

Reports

Reports are read-only.

---

# 9. Settings

Workspace Settings are optional.

Examples

Attendance Configuration

Grading Rules

Payment Rules

Notification Rules

Workspace Settings affect only the current Workspace.

---

# 10. Workspace Lifecycle

Every Workspace follows the same lifecycle.

```
Enter Workspace

↓

Dashboard

↓

Business List

↓

Business Detail

↓

Workspace Screen

↓

Complete

↓

Return
```

---

# 11. Workspace Responsibilities

Workspace owns

Navigation

Dashboard

Business Flow

Business Rules

Services

Repositories

Events

Workspace never owns another Workspace.

---

# 12. Dashboard Components

Recommended components

Statistics Cards

Pending Tasks

Recent Activity

Quick Access

Notification Panel

Workspace Announcement

Recent Objects

Dashboard layout should remain lightweight.

---

# 13. Business List Components

Required

Toolbar

Search

Filter

Table/List

Pagination

Bulk Actions

Optional

Export

Import

Saved Views

---

# 14. Business Detail Components

Recommended

Header

Summary

Tabs

Timeline

Attachments

Related Objects

Activity History

Metadata

Business Detail should remain readable.

---

# 15. Workspace Screen Components

Workspace Screen usually contains

Working Area

Context Panel

Action Toolbar

Status Indicator

Validation Messages

Workspace Screen prioritizes productivity.

---

# 16. Common Layout

Every Workspace should follow the same page structure.

```
Header

↓

Workspace Navigation

↓

Page Toolbar

↓

Main Content

↓

Side Panel (optional)

↓

Status Bar
```

Consistency is more important than creativity.

---

# 17. Naming Convention

Dashboard

Always

```
Workspace Name + Dashboard
```

Examples

Teacher Dashboard

Finance Dashboard

Student Dashboard

Business List

Plural

```
Students

Courses

Invoices

Employees
```

Business Detail

Singular

```
Student Detail

Course Detail

Invoice Detail
```

Workspace Screen

```
Teaching Workspace

Assessment Workspace

Payroll Workspace
```

---

# 18. Workspace Communication

Workspace communicates through

Services

Domain Events

API

Never through direct UI manipulation.

Example

Teacher Workspace

↓

Student Highlight Event

↓

Student Workspace updates Timeline

---

# 19. Workspace Ownership

Every business object belongs to exactly one Workspace.

Examples

Student

Student Workspace

Session

Teacher Workspace

Invoice

Finance Workspace

Employee

HR Workspace

No shared ownership.

---

# 20. Workspace Permission

Permission is granted per Workspace.

Examples

Teacher

Teacher Workspace

Read Student Workspace

No Finance Workspace

Manager

All Workspaces

Reception

Student Workspace

Finance Workspace

Permission should never depend on individual pages.

---

# 21. Workspace Expansion

Future Workspaces should follow exactly the same architecture.

Examples

Inventory Workspace

Library Workspace

CRM Workspace

Marketing Workspace

AI Workspace

Equipment Workspace

No special treatment is required.

---

# 22. Workspace Anti-patterns

The following are prohibited.

❌ Dashboard performing CRUD

❌ Business logic inside Home

❌ Cross Workspace editing

❌ Mixed business objects

❌ Different navigation styles

❌ Duplicate business ownership

---

# 23. Workspace Quality Checklist

Before releasing a Workspace

Verify

□ Dashboard exists

□ Business List exists

□ Business Detail exists

□ Workspace Screen exists

□ Reports available

□ Navigation follows standard

□ Permission implemented

□ Breadcrumb correct

□ Responsive layout

□ Consistent terminology

---

# 24. Workspace Principles

Principle 1

One Workspace = One Business Domain

---

Principle 2

Dashboard summarizes.

Workspace performs.

---

Principle 3

Business Lists locate.

Business Details explain.

Workspace Screens execute.

---

Principle 4

Every Workspace should feel familiar.

Learning one Workspace should reduce learning cost for every other Workspace.

---

Principle 5

Consistency is preferred over customization.

---

# 25. Future Vision

CenterManager should evolve as a collection of independent Workspaces.

Each Workspace may eventually become an independent module while maintaining the same user experience.

The Workspace Specification guarantees long-term scalability and architectural consistency.

---

# Workspace Status

Version

2.0

Status

APPROVED

Frozen

YES

Mandatory

YES