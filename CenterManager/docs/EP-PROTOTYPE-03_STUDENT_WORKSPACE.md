# EP-PROTOTYPE-03 — Student Workspace

Status: **PROPOSED FOR REVIEW**

Baseline: `b5bfe0c8d63638bcb42ca57a0465d8e03d191b89` (merged EP-PROTOTYPE-02)

## 1. Purpose

Freeze the Student Workspace contract for the prototype without introducing a second student-management architecture.

This task validates the existing implementation against the approved prototype scope. If the existing implementation already satisfies the contract, no production refactor is required.

## 2. Prototype Role

Student Workspace is the first business workspace in the Golden Flow:

```text
Home
  ↓
Student Workspace
  ↓
Student List
  ↓
Student Detail
  ↓
Class / Enrollment context
  ↓
Session / Attendance / Assessment
  ↓
Student Timeline
```

The workspace is responsible for navigation and presentation. Existing services remain responsible for business operations.

## 3. Required Workspace Structure

The workspace must expose these application-level concepts:

```text
Student Workspace
  ├── Dashboard
  ├── Students
  │    └── Student Detail
  └── Analytics (existing product surface)
```

The prototype-critical path is **Students → Student Detail**. Dashboard and Analytics are retained existing surfaces and are not required to expand the prototype scope.

## 4. Student List Contract

Student List must support the prototype's minimum capability to find/select a student.

Existing implementation may provide additional data-management functions, including search, filtering, refresh, add, import, export, sorting, selection and context actions. These are existing capabilities and are not redefined by this prototype task.

The required boundary is:

- list owns student-list presentation;
- selecting a student emits/propagates the selected student ID;
- workspace opens the corresponding Student Detail;
- list does not become the owner of Student Detail business state.

## 5. Student Detail Contract

Student Detail is the business-context hub for the selected student.

Minimum prototype information/context:

- core student profile information;
- class/enrollment context;
- learning/activity timeline.

The existing implementation also exposes related product surfaces such as:

- Profile;
- Enrollment;
- Financial (permission protected);
- Attendance;
- Reports;
- Assessment;
- Timeline;
- Notes and supporting student information.

These existing surfaces must not be removed or duplicated merely for the prototype.

## 6. Selected Student Context

The Student Workspace must maintain the currently selected student ID while the user is inside the workspace.

Required behavior:

```text
Select student
    ↓
Store current student ID
    ↓
Load Student Detail for that ID
    ↓
Display related student context
```

Returning from detail to the student list must preserve the workspace-level navigation model. Opening a student from dashboard and from list should converge on the same Student Detail path.

## 7. Golden-Flow Cross-Context Contract

Student Workspace must provide the entry point for continuing the Golden Flow into related Class/Session operations.

The Student Workspace itself does not need to own Class, Session, Attendance, or Assessment business logic. It only needs to expose the existing context/navigation hooks required to continue the flow.

The prototype therefore distinguishes:

- **Student Workspace responsibility:** student discovery, selected-student context, detail presentation and navigation hooks.
- **Related workspace responsibility:** class/session/attendance/assessment operations.
- **Service responsibility:** business rules and persistence.

## 8. Navigation Contract

The following transitions are part of this task:

```text
Student Workspace / Dashboard
        ↓ select student
Student Detail
        ↓ Back
Student List
```

Student Detail may emit a finance-navigation request for the existing Finance Workspace. This is a cross-workspace navigation hook, not ownership of the Finance Workspace.

## 9. Permission / Platform Boundary

The workspace must continue using the existing platform and permission boundaries.

In particular:

- write-state propagation remains centralized at the workspace boundary;
- Student Detail keeps finance visibility permission-protected;
- existing WriteGuard/PermissionGuard mechanisms are reused;
- this task does not redesign authorization.

## 10. Non-Goals

EP-PROTOTYPE-03 does not introduce:

- a new Student domain model;
- a new Student service layer;
- a new router;
- a second Student Detail implementation;
- a new repository abstraction;
- a new event bus;
- a redesign of existing student CRUD;
- a redesign of analytics, reporting, finance, or permissions;
- broad visual restyling.

## 11. Implementation Decision

The current codebase already contains the required Student Workspace shell, Student List, and Student Detail implementation. Therefore this task is a **contract-and-regression task** unless source audit identifies a concrete gap.

No production change should be made solely to satisfy the regression test.

## 12. Acceptance Gate

EP-PROTOTYPE-03 is accepted when:

1. Student Workspace registers Dashboard, Students and Analytics navigation.
2. Student selection from the list reaches Student Detail with the selected ID.
3. Dashboard student selection converges on the same detail path.
4. Student Detail contains the required Profile, Enrollment and Timeline context.
5. Student Detail provides the existing hooks for Attendance, Assessment and related operations.
6. Returning from detail reaches the student list.
7. Existing permission/platform boundaries remain in place.
8. The targeted regression test and existing architecture/prototype regression tests remain green.
