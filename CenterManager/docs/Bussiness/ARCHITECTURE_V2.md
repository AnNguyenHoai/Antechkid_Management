# CenterManager Architecture V2

Version: 2.0

Status: APPROVED

Author: Architecture Team

---

# 1. Vision

CenterManager is **NOT** a Student Management System.

CenterManager is a **Workspace Platform** for operating an education center.

Every business area is represented by an independent Workspace.

Users enter the system through the Home Page, choose a Workspace, and complete their work inside that Workspace.

---

# 2. Core Philosophy

The Home Page does NOT contain business logic.

The Home Page is a Workspace Launcher.

Business logic exists only inside Workspaces.

---

# 3. Architecture Overview

```
                    CenterManager

                       Home

                         │

 ┌────────────┬────────────┬────────────┬────────────┐

 Student WS   Teacher WS   Finance WS    HR WS

 └────────────┴────────────┴────────────┴────────────┘

                  Report WS

                  Admin WS
```

---

# 4. Home Page

Purpose

- Entry point of the system
- Launch Workspaces
- No business workflow
- No CRUD
- No Student List
- No Session List

Example

```
CenterManager

-------------------------------------

👨‍🎓 Student Workspace

-------------------------------------

👨‍🏫 Teacher Workspace

-------------------------------------

💰 Finance Workspace

-------------------------------------

👥 Human Resources

-------------------------------------

📊 Reports

-------------------------------------

⚙ Administration
```

Home Page remains simple regardless of future expansion.

---

# 5. Workspace Definition

A Workspace is an independent business area.

Each Workspace owns:

- Navigation
- Dashboard
- Business Flow
- UI
- Services
- Domain
- Repository

A Workspace should not own another Workspace.

---

# 6. Student Workspace

Purpose

Manage student information and learning history.

Structure

```
Student List

↓

Student Detail

    ├── Summary

    ├── Assessment

    ├── Timeline

    ├── Parents

    ├── Products

    └── Attachments
```

Responsibilities

- Student Profile
- Parent Management
- Learning Review
- Timeline
- Portfolio

This Workspace is history-oriented.

---

# 7. Teacher Workspace

Purpose

Support daily teaching activities.

Structure

```
Courses

↓

Classes

↓

Sessions

↓

Teaching Workspace

      ├── Attendance

      ├── Teaching Note

      ├── Student Highlight

      ├── Homework

      ├── Lesson Material

      └── Future Extensions
```

Responsibilities

- Daily teaching
- Session management
- Classroom activities

This Workspace is operation-oriented.

---

# 8. Finance Workspace

Purpose

Manage financial operations.

Example

```
Invoices

↓

Payments

↓

Salary

↓

Expense

↓

Revenue
```

---

# 9. Human Resource Workspace

Purpose

Manage teachers and employees.

Example

```
Employees

↓

Teachers

↓

Leave

↓

Payroll

↓

Contracts
```

---

# 10. Report Workspace

Purpose

Business analytics.

Examples

- Student Progress
- Attendance Report
- Financial Report
- Teacher KPI
- Center KPI

Reports are read-only.

---

# 11. Administration Workspace

Purpose

System configuration.

Examples

- User Management
- Roles
- Permissions
- Backup
- Settings

---

# 12. Domain Architecture

```
CenterManager

├── Student Domain

├── Teaching Domain

├── Finance Domain

├── HR Domain

├── Report Domain

└── Administration Domain
```

Every Domain is independent.

Communication happens only through Services or Domain Events.

---

# 13. UI Architecture

```
ui/

    home/

    student/

    teacher/

    finance/

    hr/

    report/

    admin/
```

Never mix different business domains inside one UI module.

---

# 14. Service Architecture

```
services/

    student/

    teacher/

    finance/

    hr/

    report/

    admin/
```

---

# 15. Repository Architecture

```
repositories/

    student/

    teacher/

    finance/

    hr/

    report/

    admin/
```

---

# 16. Database Naming

Current implementation may use one database.

Tables should be grouped logically.

Example

```
student_*

teacher_*

finance_*

hr_*

report_*
```

Avoid mixing unrelated tables.

---

# 17. Workspace Independence

Teacher Workspace should NOT directly edit Student Summary.

Student Workspace should NOT manage Sessions.

Finance should NOT manage Teaching Notes.

Every Workspace owns its own business.

---

# 18. Dashboard Philosophy

Every Workspace has its own Dashboard.

Example

Teacher Workspace

```
Today's Classes

Pending Attendance

Pending Session Notes

Upcoming Classes
```

Student Workspace

```
New Students

Pending Reviews

Recently Updated Students
```

Dashboard belongs to Workspace.

NOT Home Page.

---

# 19. Future Expansion

Future Workspaces may include

- Inventory
- Library
- CRM
- Marketing
- AI Assistant
- Equipment Management
- Parent Portal

Adding a new Workspace should not require changing existing Workspaces.

---

# 20. Architecture Principles

Principle 1

Home Page is only a Workspace Launcher.

---

Principle 2

One Workspace = One Business Context.

---

Principle 3

One Domain = One Responsibility.

---

Principle 4

Cross-domain communication must use Services or Events.

---

Principle 5

No Workspace owns another Workspace.

---

Principle 6

Workflows live inside Workspaces.

Never on Home Page.

---

# 21. Long-Term Goal

CenterManager should evolve into a modular Education ERP.

Every new capability should belong to exactly one Workspace.

The architecture must support continuous expansion without major refactoring.

---

# Architecture Status

Architecture Version

V2

Status

APPROVED

Frozen

YES

Breaking Changes Allowed

NO