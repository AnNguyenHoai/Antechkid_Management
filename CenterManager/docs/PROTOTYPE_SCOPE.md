# EP-PROTOTYPE-01 — Prototype Scope & UX Contract

Status: **PROPOSED FOR REVIEW**

Baseline: `b63a7afa0a8f2e2d36c602ee2573a3cd36a53371`

## 1. Purpose

This document freezes the minimum product scope for the first CenterManager prototype.

The prototype is intended to validate one coherent, end-to-end operating flow rather than implement the full product surface.

This contract is a **product/UX boundary only**. It does not introduce a new application architecture, persistence model, or UI framework.

## 2. Existing Product Contracts Used

The prototype follows the repository's already approved product architecture:

- `docs/Bussiness/ARCHITECTURE_V2.md`
- `docs/Bussiness/NAVIGATION.md`
- `docs/Bussiness/WORKSPACE_SPEC.md`
- `docs/Bussiness/INFORMATION_ARCHITECTURE_V3.md`

These documents establish CenterManager as a Workspace Platform, with Home as the entry point and business work occurring inside Workspaces.

## 3. Prototype Goal

The prototype must allow a reviewer to understand the product through a real education-center workflow:

```text
Student
  ↓
Class
  ↓
Teacher
  ↓
Session
  ↓
Attendance
  ↓
Assessment
  ↓
Student Timeline
```

A secondary finance flow validates the basic center cash/bank operating view:

```text
Income
  ↓
Expense
  ↓
Balance
```

The prototype does not attempt to cover every approved business object or every existing service.

## 4. Prototype Scope

### P0 — Application Entry

Home acts as the Workspace Launcher.

It provides entry points for the prototype workspaces without owning CRUD or business workflow.

### P1 — Student Workspace

Prototype screens:

```text
Student Workspace
  ├── Student List
  └── Student Detail
       ├── Summary
       ├── Classes / Enrollment context
       └── Timeline
```

Minimum user capability:

- Find/select a student.
- View core student information.
- See the student's current class/enrollment context.
- Open the student's learning/activity timeline.

### P2 — Class Workspace

Prototype screens:

```text
Class Workspace
  ├── Class List
  └── Class Detail
       ├── Overview
       ├── Teacher
       ├── Students
       └── Sessions
```

Minimum user capability:

- Find/select a class.
- View assigned teacher.
- View enrolled students.
- Open a session.

### P3 — Teacher Workspace

Prototype screens:

```text
Teacher Workspace
  ├── Teacher List
  └── Teacher Detail
       ├── Overview
       ├── Assigned Classes
       └── Sessions
```

Minimum user capability:

- Find/select a teacher.
- View assigned classes.
- Navigate to relevant sessions.

### P4 — Session

Session is the primary operational workspace of the prototype.

Minimum information:

- Class
- Teacher
- Date/time
- Topic or lesson context
- Session students

### P5 — Attendance

Attendance is completed from the selected session.

Minimum operation:

```text
Session
  ↓
Student roster
  ↓
Present / Absent
```

### P6 — Assessment

Assessment is recorded in the context of a session/student.

Minimum prototype fields:

- Understanding
- Practice
- Homework
- Note

The prototype does not define a new assessment engine or grading framework.

### P7 — Student Timeline

The timeline connects the learning flow back to the Student Workspace.

Minimum visible event types:

- Session/activity
- Attendance result
- Assessment recorded

Example:

```text
17/09/2026
Python Basic — Session 03
Present
Assessment recorded
```

### P8 — Finance Basic

The finance prototype is intentionally small.

Minimum screens:

```text
Finance Workspace
  ├── Income
  ├── Expense
  └── Balance
```

Minimum information:

- Income records
- Expense records
- Cash total
- Bank-transfer total
- Balance summary

This slice is not an accounting system.

### P9 — Dashboard Integration

The prototype dashboard may summarize already available data from the prototype flows.

Minimum summary:

- Students
- Active classes
- Teachers
- Sessions
- Finance balance

Dashboard is informational and does not own CRUD operations.

## 5. Golden Flow Acceptance Criteria

### Golden Flow A — Learning Operation

A reviewer must be able to complete the following flow without leaving the application:

```text
Open Home
  ↓
Open Student Workspace
  ↓
Open Student
  ↓
View Class / Enrollment
  ↓
Open Class
  ↓
Open Session
  ↓
Mark Attendance
  ↓
Record Assessment
  ↓
Return to Student
  ↓
See Timeline update
```

### Golden Flow B — Finance

A reviewer must be able to:

```text
Open Finance
  ↓
View Income
  ↓
View Expense
  ↓
View Balance
```

## 6. Navigation Contract

The prototype follows the approved Workspace-first model:

```text
CenterManager
  ↓
Home
  ↓
Workspace
  ↓
Business List
  ↓
Business Detail
  ↓
Operational Workspace
```

Cross-workspace navigation must preserve the current business context when moving between related Student, Class, Teacher, and Session views.

## 7. Prototype Non-Goals

The following are explicitly outside EP-PROTOTYPE-01:

- Full product implementation.
- New event-bus architecture.
- CQRS or new application layers.
- New repository abstractions.
- Advanced permission redesign.
- Full accounting functionality.
- Reporting/analytics platform.
- Notifications/automation platform.
- Performance optimization unrelated to a demonstrated prototype problem.
- Broad architecture refactoring merely to satisfy this scope document.

## 8. Implementation Rules for Follow-up Prototype Tasks

1. Reuse existing services, repositories, domain objects, and navigation concepts whenever they already satisfy the contract.
2. Do not introduce a new technical abstraction unless an existing boundary cannot support the required prototype behavior.
3. Keep business behavior changes explicit and local to the prototype task that needs them.
4. Every prototype feature must be testable at the relevant application/service boundary.
5. Prototype UX should be validated through the Golden Flow, not through isolated screens alone.

## 9. Prototype Completion Gate

EP-PROTOTYPE phase is considered viable only when all of the following are demonstrated:

- Home can enter the prototype workspaces.
- Student → Class → Teacher → Session is navigable.
- Attendance can be recorded for a session.
- Assessment can be recorded for a student/session.
- Student Timeline reflects the resulting learning activity.
- Finance Income/Expense/Balance can be viewed through one coherent workspace flow.
- Existing architecture regression tests remain green.

## 10. Out-of-Scope Decisions Deferred Until UAT

The following remain intentionally open until the prototype is manually exercised:

- Final visual styling.
- Exact table/card layouts.
- Final terminology where existing product documents conflict with implemented labels.
- Advanced filtering/search behavior.
- Mobile/responsive behavior.
- Advanced role-specific navigation.

These decisions should be made from actual prototype feedback rather than pre-optimizing the architecture.
