# CenterManager — Workspace Model

Version: 1.1  
Status: **APPROVED WORKSPACE MODEL**  
Updated: 2026-09-24

Depends on:

- `000_PLATFORM_VISION.md`
- `100_ARCHITECTURE_PRINCIPLES.md`
- `200_COLLABORATIVE_ARCHITECTURE.md`

This document defines what a Workspace means in CenterManager. It does not mandate a universal runtime state machine that every UI package must literally implement.

## 1. Definition

A Workspace is a bounded operational/presentation context for one coherent business area.

Examples in the current product include Student, Class/Teaching, Finance, Employee/Teacher and Administration workspaces.

A Workspace is more than a single page, but it is not the owner of persistence, synchronization or another domain's business rules.

## 2. Responsibilities

A Workspace may own:

- navigation within its business area;
- views/dialogs/forms;
- dashboard/read projections;
- user interaction flow;
- selected-object/filter/presentation state;
- projection of collaboration/capability/domain state;
- refresh behavior.

A Workspace does not own:

- SQLAlchemy persistence;
- Git synchronization;
- global collaboration/edit-session protocol;
- another domain's canonical rules;
- permission definitions that already belong to the authorization system.

## 3. Current implementation

Current workspace UI packages live under `src/centermanager/ui/`.

The repository currently includes workspace packages such as:

- `student_workspace/`;
- `class_workspace/`;
- `finance_workspace/`;
- `employee_workspace/`;
- `admin_workspace/`;
- `home/` and shared application-shell/design-system components.

Services and repositories are currently mostly shared/flat packages. Workspace ownership is a product/domain concept, not a requirement to duplicate every layer under each workspace folder.

## 4. Application shell and activation

The application shell/MainWindow coordinates top-level navigation and current workspace presentation.

A workspace should not instantiate or directly manipulate another workspace's internal widgets/state as a way to perform business operations.

Cross-workspace refresh/navigation should use established shell/application/event/service contracts.

## 5. Collaboration participation

Workspaces consume collaboration/platform state; they do not own collaboration.

A workspace can:

- reflect read/write mode;
- participate in the established edit-session/write workflow;
- refresh after relevant events/version changes;
- display synchronization/locked/error state;
- disable/hide mutation controls when capability/domain state requires it.

A workspace must not:

- run its own Git sync loop;
- manage platform metadata directly;
- treat WRITE state as sufficient authorization.

## 6. Workspace state

Not every workspace is required to implement the old conceptual sequence `UNINITIALIZED → INITIALIZING → READY → ACTIVE → EDITING → SYNCING → DISPOSED` as a concrete enum/state machine.

The durable requirement is that a workspace handles relevant UI/application states explicitly and consistently, such as:

- initialization/loading;
- ready/active presentation;
- read vs write collaboration state where applicable;
- permission-denied state;
- domain-locked state;
- synchronization/refresh state;
- error/empty state;
- disposal/lifecycle cleanup when required by the shell.

Exact state implementation belongs to the application shell/workspace code and task-specific contracts.

## 7. Workspace communication

Avoid direct workspace-to-workspace mutation.

Preferred communication paths:

```text
Workspace UI
   ↓
Application Service / Shared Read Model
   ↓
Domain / Repository
```

and for decoupled updates:

```text
Domain/Application change
   ↓
Event / refresh signal
   ↓
Workspace projection refresh
```

A direct import is not automatically forbidden when it is a shared UI component or shell contract; the prohibited pattern is using another workspace's internals as a business API.

## 8. Domain ownership

A workspace presents a domain; it does not redefine the domain.

Examples:

- Finance Workspace uses Finance services/specs for FinancePeriod/ledger rules;
- Student Workspace uses Student services for student lifecycle/history;
- Class Workspace uses Class/Enrollment/Session services;
- Employee Workspace uses Employee/Teacher services;
- Admin Workspace uses administration/authorization/configuration services.

## 9. Refresh policy

Refresh should be event/state driven where possible and may also support explicit user refresh.

Do not implement continuous storage/Git polling inside workspaces. Platform owns synchronization/version monitoring.

Workspace-specific refresh may respond to application events or shell/navigation lifecycle when that is the established pattern.

## 10. Workspace context

Workspace context can include presentation-relevant state such as:

- current authenticated user/capabilities;
- collaboration/read-write state;
- selected entity/filter/context;
- domain-specific selected context (for example canonical FinancePeriod);
- refresh/version signals.

Do not duplicate authoritative domain entities/calculations into ad-hoc UI context objects. Context should carry identity/state needed to call authoritative services.

## 11. Finance example

Finance Workspace is a useful example of the intended model.

The UI can preserve a selected canonical FinancePeriod across Dashboard, Income, Expense, Outstanding and Settlement, but it must not calculate a new Month/Year accounting period itself.

Likewise, the UI can disable mutation for a closed period, while the service/domain guard remains authoritative.

## 12. Workspace registration

Platform/bootstrap/application shell may register or construct workspace definitions as needed by current implementation.

Do not assume an old conceptual `WorkspaceManager.register(StudentWorkspace)` API exists unless verified in current code.

The architectural requirement is centralized shell/platform ownership of workspace availability/navigation, not a specific historical class name.

## 13. Extension

Future workspace candidates may include CRM, Inventory, Parent Portal or specialized Reporting.

Before adding one, establish:

- clear business/domain owner;
- whether it is truly a workspace rather than a page within an existing workspace;
- service/read-model dependencies;
- authorization boundaries;
- how it participates in collaboration/refresh without owning infrastructure.

## 14. Architectural rules

1. Workspace owns business-area presentation/workflow context.
2. Workspace does not own database/synchronization infrastructure.
3. Workspace does not duplicate another domain's business rules.
4. Cross-workspace business behavior uses services/read models/events.
5. Platform owns collaboration/synchronization.
6. UI state projection does not replace service authorization/domain guards.
7. Conceptual workspace boundaries do not require artificial package nesting.
8. Exact lifecycle/state enums must reflect actual implementation, not stale diagrams.

## 15. Related documents

- `docs/Bussiness/ARCHITECTURE_V2.md` — product/workspace architecture;
- `docs/ARCHITECTURE.md` — current implementation architecture;
- `200_COLLABORATIVE_ARCHITECTURE.md` — platform collaboration responsibilities;
- domain specs — authoritative business/domain semantics;
- root `AGENTS.md` — developer/agent workflow.