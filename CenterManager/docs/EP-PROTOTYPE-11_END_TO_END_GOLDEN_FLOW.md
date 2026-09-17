# EP-PROTOTYPE-11 — End-to-End Golden Flow

## Purpose
Freeze the end-to-end operational contract that connects the prototype workspaces without introducing a second navigation or business layer.

## Golden Flow

```text
Open CenterManager
  ↓
Home Dashboard
  ↓
Student Workspace
  ↓
Class / Teacher context
  ↓
Session / Operational Workspace
  ↓
Attendance + Assessment
  ↓
Student Timeline
  ↓
Finance
  ↓
Return Home
```

The flow is a cross-workspace integration contract, not a requirement to redesign existing screens or move business logic into the UI.

## Required scope

- `HomePage` remains the application entry surface.
- Home selection is emitted as a stable workspace identifier.
- `MainWindow` remains the application-level router and permission gate.
- Student, Teacher, Class, Finance, Employee, and Admin continue to use their existing workspace shells.
- Student detail exposes Enrollment, Attendance, Assessment, and Timeline surfaces through existing services/widgets.
- Class detail exposes schedule/session operations through the existing Class Workspace flow.
- Session detail exposes Attendance and Teaching Overview through the existing operational session flow.
- Finance continues to expose Dashboard, Income, Expense, and Outstanding surfaces.
- Returning Home refreshes the Home Dashboard rather than creating a parallel dashboard state.

## Boundary contract

- UI pages/widgets coordinate presentation and user navigation only.
- Existing services remain responsible for business operations and persistence.
- `MainWindow` owns only application-level workspace composition/routing.
- Workspace shells own internal workspace navigation.
- No UI layer directly replaces service/repository responsibilities.
- No second application router or parallel persistence path is introduced.

## Regression gate

The EP-PROTOTYPE-11 tests verify the cross-workspace composition statically from source so the contract remains stable without requiring a GUI session in CI.

## Non-goals

- No visual redesign.
- No new business entities or CRUD semantics.
- No replacement of existing workspace shells.
- No new routing framework.
- No new service/repository layer.
- No end-to-end test that depends on a live desktop display in CI.

## Completion gate

1. EP-PROTOTYPE-11 targeted tests pass.
2. Full regression suite passes.
3. Production behavior is unchanged unless a concrete integration defect is discovered by the audit.
