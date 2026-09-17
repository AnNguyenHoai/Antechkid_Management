# EP-PROTOTYPE-05 — Teacher Workspace

## Purpose

Freeze the minimum Teacher Workspace contract for the prototype. The existing implementation already provides the required flow, so this task adds regression protection without changing production behavior.

## Prototype Flow

```text
Teacher Workspace
  ├── Dashboard
  └── Teachers
       ↓
   Teacher Detail
       ├── Professional Information
       ├── Assigned Classes
       ├── Documents
       └── Timeline
```

## Required Behavior

- Teacher Workspace exposes Dashboard and Teachers navigation.
- Selecting a teacher converges on Teacher Detail.
- The selected teacher ID is retained at workspace level.
- Teacher Detail exposes teacher identity and professional information.
- Teacher Detail exposes assigned classes.
- Assigned class entries provide a cross-workspace navigation hook to Class Workspace.
- Teacher Detail exposes documents and timeline context.
- Back from Teacher Detail returns to the Teacher list.
- Teacher mutations refresh dependent Teacher Workspace projections.
- Write operations remain guarded by the existing collaboration/write boundary.
- Class-assignment management retains its Admin/Manager authorization boundary.

## Architecture Constraints

- Reuse the existing WorkspaceNavigation and QStackedWidget pattern.
- Reuse existing TeacherService and related service boundaries.
- Do not introduce a second Teacher router.
- Do not introduce a new Teacher service/repository abstraction.
- Do not move business CRUD responsibility into the workspace shell.

## Golden Flow Contribution

```text
Open Teacher Workspace
  ↓
Select Teacher
  ↓
View Assigned Classes
  ↓
Open Class
```

The Class Workspace remains responsible for Class context and session operations.
