# EP-PROTOTYPE-02 — Application Shell & Navigation

Status: **PROPOSED FOR REVIEW**

## 1. Purpose

Implement the application shell needed by the CenterManager prototype while reusing the existing Qt application shell and workspace widgets.

## 2. Baseline Observation

The current application already provides the required shell primitives:

- `run.py` bootstraps `centermanager.app.main()`.
- `app.py` creates the `MainWindow` after platform, database, authentication, and service initialization.
- `MainWindow` owns a `QStackedWidget` as the application-level page stack.
- `HomePage` emits `workspace_selected` and acts as the workspace launcher.
- `MainWindow` connects workspace selection to the existing Student, Teacher, Class, Finance, Employee, and Admin workspace shells.
- Existing workspace shells retain their own internal navigation.

Therefore this task does **not** introduce a second router, replace the existing shell, or refactor workspace internals.

## 3. Prototype Application Shell

The application-level hierarchy is:

```text
CenterManager
  ↓
Home
  ↓
Prototype Workspace
  ├── Student Workspace
  ├── Class Workspace
  ├── Teacher Workspace
  └── Finance Workspace
```

Existing Employee and Administration workspaces remain available but are outside the core prototype Golden Flow.

## 4. Navigation Contract

### Application entry

The application starts at `Home` after successful authentication.

### Home → Workspace

`HomePage.workspace_selected` is the single application-shell entry signal for workspace selection.

### Workspace IDs

The prototype uses these stable IDs:

| ID | Workspace |
|---|---|
| `student` | Student Workspace |
| `class` | Class Workspace |
| `teacher` | Teacher Workspace |
| `finance` | Finance Workspace |

Existing IDs retained by the application shell:

| ID | Workspace |
|---|---|
| `employee` | Employee Workspace |
| `admin` | Administration Workspace |

### Back to Home

Workspace shells expose `go_home`; `MainWindow._go_home()` returns the application to Home.

### Cross-workspace navigation

The application shell may route to another workspace when an existing feature requires it. The destination workspace owns its own internal detail/navigation state.

## 5. Prototype Navigation Acceptance

The following must be true:

1. Home is the initial application-level page.
2. Home can open Student, Class, Teacher, and Finance workspaces.
3. Selecting a workspace changes the `QStackedWidget` current widget to the corresponding existing workspace shell.
4. Permission checks remain enforced before protected workspace entry.
5. Workspace `go_home` signals return to Home.
6. Application-shell navigation does not perform business CRUD.
7. Existing workspace-internal navigation remains owned by each workspace shell.
8. The shell does not introduce a new repository/service architecture.

## 6. Out of Scope

- Rebuilding existing workspace pages.
- Creating Student/Class/Teacher/Finance business functionality.
- New navigation framework or routing dependency.
- New authentication model.
- Visual redesign of every workspace.
- Mobile/responsive navigation.

## 7. Implementation Decision

The source audit found that the required application shell and navigation behavior already exist in the current codebase. The implementation for this task therefore consists of a regression contract that freezes the existing shell behavior while the remaining prototype slices are implemented.

A production navigation refactor should only be introduced if a later prototype flow demonstrates a concrete limitation in the current shell.
