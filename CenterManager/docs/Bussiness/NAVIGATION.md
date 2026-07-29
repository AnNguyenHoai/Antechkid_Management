# NAVIGATION.md

Version: 2.0

Status: APPROVED

Architecture Level: Product

Depends On:

- ARCHITECTURE_V2.md

---

# 1. Purpose

This document defines the navigation architecture of CenterManager.

It specifies:

- Navigation hierarchy
- Workspace entry points
- Screen transitions
- Navigation rules
- Cross-workspace navigation
- Breadcrumb behavior

This document does NOT define UI appearance.

It only defines how users move through the system.

---

# 2. Navigation Philosophy

CenterManager uses a Workspace-first navigation model.

Users always begin at Home.

Business operations happen inside Workspaces.

Navigation should feel natural and predictable.

Every screen should answer one question:

"Where am I?"

and

"Where can I go next?"

---

# 3. Navigation Hierarchy

```

CenterManager

↓

Home

↓

Workspace

↓

Dashboard

↓

Business Pages

↓

Business Detail

↓

Business Workspace

```

Example

```

Home

↓

Teacher Workspace

↓

Teacher Dashboard

↓

Courses

↓

Classes

↓

Sessions

↓

Teaching Workspace

```

---

# 4. Navigation Levels

There are six navigation levels.

Level 0

System

Example

```
CenterManager
```

---

Level 1

Home

```
Home
```

Purpose

Workspace Launcher

---

Level 2

Workspace

```
Teacher Workspace

Student Workspace

Finance Workspace

HR Workspace

Report Workspace

Administration Workspace
```

---

Level 3

Dashboard

Every Workspace owns its own dashboard.

Example

```
Teacher Dashboard

Student Dashboard

Finance Dashboard
```

Dashboard summarizes the current Workspace.

---

Level 4

Business Pages

Examples

```
Courses

Students

Invoices

Employees
```

Business Pages usually contain tables or lists.

---

Level 5

Business Detail

Examples

```
Student Detail

Course Detail

Invoice Detail

Employee Detail
```

---

Level 6

Business Workspace

This is where actual work happens.

Examples

```
Teaching Workspace

Invoice Workspace

Assessment Workspace

Payroll Workspace
```

---

# 5. Workspace Navigation

## Student Workspace

```

Home

↓

Student Workspace

↓

Student Dashboard

↓

Student List

↓

Student Detail

├── Summary

├── Timeline

├── Assessment

├── Parent

└── Portfolio

```

---

## Teacher Workspace

```

Home

↓

Teacher Workspace

↓

Teacher Dashboard

↓

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

└── Lesson Material

```

---

## Finance Workspace

```

Home

↓

Finance Workspace

↓

Finance Dashboard

↓

Invoices

↓

Invoice Detail

↓

Payment

```

---

## HR Workspace

```

Home

↓

HR Workspace

↓

Employee List

↓

Employee Detail

```

---

## Report Workspace

```

Home

↓

Report Workspace

↓

Reports

↓

Report Detail

```

---

# 6. Navigation Rules

Rule 1

Users always enter through Home.

Never directly open a Business Page after login.

---

Rule 2

Every Workspace owns its own navigation.

Teacher navigation never appears inside Student Workspace.

---

Rule 3

Business flows never cross Workspaces.

Example

Teaching Workspace

must NOT open

Student Dashboard.

---

Rule 4

Returning to Home should always be possible.

Home acts as the global navigation hub.

---

Rule 5

Back navigation should return to the previous business context.

Example

```

Teaching Workspace

↓

Session List

↓

Class List

↓

Course List

↓

Teacher Dashboard

```

Never jump directly back to Home.

---

# 7. Breadcrumb

Every screen above Dashboard level should display Breadcrumb.

Example

```
Home

>

Teacher Workspace

>

Courses

>

Python Beginner

>

Class A

>

Session 5
```

---

# 8. Workspace Switching

Workspace switching only happens through Home.

Correct

```

Home

↓

Teacher Workspace

```

Back

↓

Home

↓

Student Workspace

Incorrect

```

Teacher Workspace

↓

Student Workspace
```

Direct Workspace switching is not allowed.

---

# 9. Deep Navigation

Maximum recommended depth

```
Home

↓

Workspace

↓

Dashboard

↓

Business Page

↓

Business Detail

↓

Workspace
```

Six levels maximum.

Avoid deeper structures.

---

# 10. Navigation Consistency

Every Workspace follows the same navigation pattern.

```
Workspace

↓

Dashboard

↓

List

↓

Detail

↓

Workspace
```

This consistency reduces learning cost.

---

# 11. Global Navigation

Global navigation is always available.

Contains

- Home
- Notifications
- User Profile
- Search
- Workspace Launcher

Global navigation never contains business actions.

---

# 12. Business Navigation

Business navigation belongs to the current Workspace.

Teacher Workspace

```
Dashboard

Courses

Classes

Sessions
```

Student Workspace

```
Dashboard

Students

Assessment

Timeline
```

Finance Workspace

```
Dashboard

Invoices

Payments

Revenue
```

---

# 13. Navigation Ownership

Each Workspace owns its own navigation tree.

No Workspace may modify another Workspace's navigation.

---

# 14. Cross-Workspace Links

Cross-workspace links are references only.

Example

Teaching Workspace

↓

Student Name

↓

Open Student Workspace

↓

Student Detail

The user changes Workspace.

The current business context ends.

---

# 15. Search Behavior

Global Search

Search across Workspaces.

Selecting a result opens the corresponding Workspace.

Example

Search

↓

Student

↓

Home

↓

Student Workspace

↓

Student Detail

---

# 16. Permission

Workspace visibility depends on permission.

Example

Teacher

✓ Teacher Workspace

✓ Student Workspace (Read)

✗ Finance

✗ HR

Manager

✓ All Workspaces

---

# 17. Future Expansion

New Workspaces should plug into Home.

No existing Workspace should require modification.

Example

Inventory Workspace

Library Workspace

CRM Workspace

Marketing Workspace

AI Workspace

---

# 18. Navigation Principles

1.

Home is the Workspace Launcher.

2.

One Workspace owns one navigation tree.

3.

Business flows never cross Workspaces.

4.

Every Workspace has its own Dashboard.

5.

Every Workspace follows the same navigation pattern.

6.

Breadcrumb must always represent the current business context.

7.

Global navigation never contains business logic.

8.

Navigation should minimize user confusion and unnecessary clicks.

---

# Navigation Status

Version

2.0

Status

APPROVED

Frozen

YES

---

# 19. Navigation Tree

The following diagram illustrates the complete navigation hierarchy.

```
CenterManager
│
├── Home
│
├── Student Workspace
│   │
│   ├── Dashboard
│   ├── Student List
│   ├── Student Detail
│   │     ├── Summary
│   │     ├── Timeline
│   │     ├── Assessment
│   │     ├── Parents
│   │     └── Portfolio
│   │
│   └── Future Features
│
├── Teacher Workspace
│   │
│   ├── Dashboard
│   ├── Courses
│   ├── Classes
│   ├── Sessions
│   │
│   └── Teaching Workspace
│          ├── Attendance
│          ├── Teaching Note
│          ├── Student Highlight
│          ├── Homework
│          └── Lesson Material
│
├── Finance Workspace
│   │
│   ├── Dashboard
│   ├── Invoice
│   ├── Payment
│   ├── Revenue
│   └── Expense
│
├── HR Workspace
│   │
│   ├── Dashboard
│   ├── Employees
│   ├── Teachers
│   ├── Payroll
│   └── Leave
│
├── Report Workspace
│   │
│   ├── Dashboard
│   ├── Student Report
│   ├── Finance Report
│   ├── Attendance Report
│   └── KPI
│
└── Administration Workspace
    │
    ├── Users
    ├── Roles
    ├── Permission
    ├── Settings
    └── Backup
```

---

# 20. Navigation State Diagram

The navigation lifecycle follows the same pattern for every Workspace.

```
Home

↓

Workspace

↓

Dashboard

↓

List

↓

Detail

↓

Workspace Screen

↓

Back

↓

Detail

↓

List

↓

Dashboard

↓

Home
```

Every Workspace must respect this lifecycle.

---

# 21. Navigation Lifecycle

Every navigation action belongs to one of the following states.

State 1

Home

Purpose

Choose business context.

---

State 2

Workspace Dashboard

Purpose

Understand current status.

---

State 3

Business List

Purpose

Locate an object.

---

State 4

Business Detail

Purpose

Inspect an object.

---

State 5

Business Workspace

Purpose

Perform business operations.

---

State 6

Complete

Return to previous context.

---

# 22. Navigation Context

Navigation always maintains a Business Context.

Example

```
Teacher Workspace

↓

Course

↓

Python Beginner

↓

Class A

↓

Session 6
```

Current Context

```
Teacher

Course

Python Beginner

Class A

Session 6
```

Every screen should know its current context.

---

# 23. Workspace Boundary

Workspace boundaries must never be broken.

Allowed

```
Teacher

↓

Session

↓

Teaching Workspace
```

Forbidden

```
Teacher Workspace

↓

Student Dashboard
```

Correct

```
Teacher Workspace

↓

Open Student

↓

Home

↓

Student Workspace

↓

Student Detail
```

Crossing a boundary always changes Workspace.

---

# 24. Navigation History

The application maintains navigation history independently for every Workspace.

Example

Teacher Workspace

```
Dashboard

↓

Course

↓

Class

↓

Session
```

User switches to

Finance Workspace

Teacher history is preserved.

Returning to Teacher Workspace restores

```
Session
```

instead of returning to Dashboard.

---

# 25. Workspace Memory

Each Workspace remembers:

- Last opened page
- Last selected object
- Current filters
- Current sorting
- Expanded panels
- Selected tabs

This improves user productivity.

---

# 26. Quick Navigation

Frequently used actions should be reachable within two clicks.

Examples

Teacher

```
Dashboard

↓

Today's Session
```

Finance

```
Dashboard

↓

Pending Invoice
```

Student

```
Dashboard

↓

Recently Updated Student
```

Quick navigation never bypasses Workspace.

---

# 27. Search Navigation

Global Search

Searches all Workspaces.

Results are grouped.

Example

```
Students

Classes

Invoices

Teachers
```

Selecting a result

Automatically enters

the correct Workspace.

Example

```
Search

↓

Student

↓

Student Workspace

↓

Student Detail
```

---

# 28. Notification Navigation

Notifications always contain

Target Workspace

Example

```
Homework not submitted

↓

Teacher Workspace

↓

Session

↓

Teaching Workspace
```

Attendance updated

↓

Student Workspace

↓

Student Detail

Notification never opens an unrelated Workspace.

---

# 29. Future Mobile Navigation

The navigation architecture should remain compatible with future mobile applications.

Recommended mapping

Desktop

```
Sidebar
```

Tablet

```
Navigation Rail
```

Mobile

```
Bottom Navigation

+

Workspace Drawer
```

Business hierarchy remains unchanged.

---

# 30. Navigation Metrics

Good navigation should satisfy the following goals.

Maximum clicks from Home

≤ 5

Maximum breadcrumb depth

≤ 6

Maximum Workspace switches

Minimal

Navigation loops

Not allowed

Dead-end pages

Not allowed

Every page must provide:

- Back
- Home
- Workspace Dashboard

---

# 31. Navigation Anti-patterns

The following patterns are prohibited.

❌ Deep nesting

```
Course

↓

Class

↓

Session

↓

Lesson

↓

Activity

↓

Exercise

↓

Submission

↓

Comment
```

---

❌ Business logic on Home

```
Home

↓

Student List
```

---

❌ Cross Workspace CRUD

Teacher

↓

Edit Invoice

---

❌ Duplicate Navigation

Finance

↓

Student Timeline

---

❌ Multiple entry points

```
Student Detail

can be opened from

Teacher

Finance

HR

Report
```

There should be one canonical navigation path.

---

# 32. Developer Guidelines

When adding a new feature

Developer must answer

1.

Which Workspace owns this feature?

2.

Does this require a new Business Page?

3.

Does this require a new Detail Page?

4.

Does this require a new Workspace Screen?

5.

Does it cross Workspace boundaries?

If yes

Architecture review is required.

---

# 33. Checklist

Before merging navigation changes

Verify

□ Workspace ownership is correct

□ Breadcrumb is correct

□ Back navigation works

□ Home navigation works

□ Permission respected

□ No Workspace leakage

□ Navigation depth acceptable

□ Search opens correct Workspace

□ Notifications open correct Workspace

□ Mobile compatibility maintained

---

# Navigation Decision

This document is part of the frozen product architecture.

Any modification to Workspace hierarchy or navigation hierarchy requires an Architecture Decision Record (ADR).

Minor UI changes (icons, menus, layout) do not require updating this document.

Major navigation changes must be reviewed and approved before implementation.