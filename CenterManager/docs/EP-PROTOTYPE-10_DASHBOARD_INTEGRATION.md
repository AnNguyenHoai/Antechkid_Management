# EP-PROTOTYPE-10 — Dashboard & Workspace Integration

## Purpose
Freeze the P10 integration contract for the Home Dashboard and the application-level workspace navigation.

## Operational flow

```text
Open CenterManager
  ↓
Home Dashboard
  ↓
Review workspace summaries
  ↓
Select Student / Teacher / Class / Finance / Employee / Admin
  ↓
MainWindow routes to the corresponding workspace
  ↓
Workspace opens its dashboard/default surface
```

## Required scope

- Home Dashboard is the application entry surface.
- Home Dashboard loads workspace summaries from `HomeDashboardService`.
- Workspace cards expose a stable `workspace_id` and emit selection events.
- `MainWindow` is the application-level composition/navigation owner.
- Workspace selection is permission-gated before navigation.
- Student, Teacher, Class, Finance, Employee, and Admin routes use their existing workspace shells.
- Returning Home refreshes the Home Dashboard.
- Home Dashboard remains an aggregation/read surface; business persistence stays in existing services.

## Boundary contract

- `HomePage` owns dashboard presentation and card selection only.
- `HomeDashboardService` owns aggregation of workspace summary data.
- `WorkspaceCard` emits the selected workspace identifier and does not perform navigation itself.
- `MainWindow` owns application-level workspace routing.
- Individual workspace shells own their internal navigation.
- No second application router, dashboard service, or persistence layer is introduced.

## Permission contract

- `student` is accessible through the existing Student workspace boundary.
- `teacher` requires `teacher.view`.
- `class` requires `class.view`.
- `finance` requires `finance.view`.
- `employee` uses the existing employee workspace access policy.
- `admin` requires `user.manage`.

## Non-goals

- No redesign of Home Dashboard visuals.
- No new KPI/accounting model.
- No new workspace implementation.
- No business CRUD changes.
- No replacement of the existing `MainWindow` stack with another router.

## Completion gate

1. Targeted EP-PROTOTYPE-10 regression tests pass.
2. Full regression suite passes.
3. No unrelated production behavior is changed.
