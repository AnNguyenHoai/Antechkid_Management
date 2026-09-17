# EP-PROTOTYPE-04 — Class Workspace

Status: **PROPOSED FOR REVIEW**

## 1. Purpose

Freeze the minimum Class Workspace contract required by the prototype Golden Flow.

The task reuses the existing Class Workspace implementation. It does not introduce a new router, service layer, repository abstraction, or persistence model.

## 2. Prototype Scope

The Class Workspace provides:

```text
Class Workspace
  ├── Dashboard
  └── Classes
       └── Class Detail
            ├── Overview
            ├── Teacher
            ├── Students
            ├── Sessions
            └── Timeline
```

## 3. Required Flow

A reviewer must be able to:

1. Enter Class Workspace from Home.
2. Open the Classes view.
3. Select a class.
4. View class overview information.
5. See assigned teacher(s).
6. See enrolled student(s).
7. See the class schedule/session surface.
8. Open the session-oriented operational surface from the class detail.
9. Return from Class Detail to the Classes list.

## 4. Business Context Contract

Class Detail must preserve the selected class context while presenting:

- class identity and status;
- course and capacity/student count context;
- assigned teachers;
- enrolled students;
- schedule/session context;
- class timeline.

The selected class ID is owned by the Class Workspace shell and is used when loading Class Detail.

## 5. Navigation Contract

Stable workspace/page IDs:

- `dashboard`
- `classes`

The shell uses the existing `WorkspaceNavigation` and `QStackedWidget` model.

Selecting a class transitions to Class Detail without introducing a second application router. Back navigation returns to `classes`.

## 6. Golden Flow Integration

Class Workspace is the bridge in the prototype learning flow:

```text
Student Detail
   ↓
Class
   ↓
Class Detail
   ↓
Session
   ↓
Attendance / Assessment
```

The workspace therefore exposes the existing session/schedule surface and preserves class context while the reviewer continues the operational flow.

## 7. Write and Permission Boundary

Write operations remain behind the existing collaboration/write boundary. Class editing, teacher assignment, student enrollment/removal, and session creation must not bypass the existing write-mode checks.

The prototype task does not redesign permissions.

## 8. Regression Rules

The contract tests must verify source-level structure without launching Qt or requiring a live database. They should protect the implemented architecture rather than prescribe incidental formatting such as quote style.

No production behavior is changed when the existing implementation already satisfies this contract.

## 9. Non-Goals

- New ClassService or repository abstraction.
- New navigation framework.
- New session engine.
- Redesign of attendance/assessment behavior.
- Broad Class Workspace visual redesign.
- Advanced filtering, reporting, or analytics beyond existing implementation.
