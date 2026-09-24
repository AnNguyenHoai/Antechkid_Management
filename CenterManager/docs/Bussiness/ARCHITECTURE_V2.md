# CenterManager Architecture V2 — Workspace/Product Architecture

Version: 2.1  
Status: **APPROVED PRODUCT ARCHITECTURE**  
Updated: 2026-09-24

This document defines the workspace/product architecture and domain ownership model. It is **not** a literal package-layout specification. Current implementation details are documented in `docs/ARCHITECTURE.md`.

## 1. Vision

CenterManager is a workspace platform for operating an education center, not merely a student-management screen set.

The Home surface launches business workspaces. Business workflows live inside their owning workspace/domain.

## 2. Product topology

```text
CenterManager
   │
   ├── Home / Application Shell
   │
   ├── Student Workspace
   ├── Class / Teaching Workspace
   ├── Employee / Teacher Workspace
   ├── Finance Workspace
   └── Administration Workspace

Shared platform capabilities:
Authentication · Authorization · Collaboration · Synchronization
Runtime Context · Events · Notifications · Logging · Version/Deployment
```

Additional report/analytics capabilities may appear as dedicated workspaces or read-only projections when product requirements justify them.

## 3. Home and application shell

Home is primarily a launcher/dashboard/navigation surface. It must not become the owner of unrelated business CRUD or domain rules.

The application shell owns cross-workspace presentation concerns such as navigation, current-user context and shared workspace framing.

## 4. Workspace definition

A Workspace represents a coherent business context and owns its user workflow/presentation semantics.

A Workspace may consume shared application/domain services, but it must not silently take ownership of another domain's business rules.

Workspace boundaries are product/domain boundaries; they do not require each workspace to have an isolated Python package for every service/repository today.

## 5. Current implementation mapping

The current code already uses workspace-oriented UI packages under `src/centermanager/ui/`, including:

- `student_workspace/`
- `class_workspace/`
- `finance_workspace/`
- `employee_workspace/`
- `admin_workspace/`
- `home/`
- shared `design_system/`

Application services and repositories are currently mostly flat under `services/` and `repositories/`.

This is intentional current implementation state. Do not reorganize services/repositories into nested domain folders merely to match a conceptual diagram. Such a refactor requires an explicit architecture task and migration plan for imports/tests.

## 6. Student Workspace

Purpose: manage student identity, family/contact context, learning history, assessments, timeline, products/documents and student-centric projections.

The Student domain is history-oriented. Other workspaces may reference student identity/history through services/read models but must not duplicate Student business rules.

## 7. Class / Teaching Workspace

Purpose: operate classes, enrollments, sessions, attendance and teaching workflows.

Typical flow:

```text
Class
  ↓
Enrollment / Assignment
  ↓
Session
  ↓
Attendance / Teaching Notes / Highlights
```

Class/Teaching owns operational learning activity; it does not become the owner of Student profile or Finance accounting semantics.

## 8. Employee / Teacher Workspace

Purpose: manage employees/teachers, assignments, schedules, working-time/work-registration, documents and teacher/employee projections.

Teacher identity may participate in class/session workflows, but HR/employee lifecycle rules remain owned by the Employee/Teacher domain.

## 9. Finance Workspace

Purpose: operate the center's accounting-oriented workflows and projections.

Current Finance Workspace concepts include:

- Finance Dashboard;
- Income;
- Expense;
- Outstanding tuition;
- FinancePeriod configuration/context;
- Settlement;
- canonical Wallet projection (`CASH`, `BANK`).

Finance Wallet V2 business semantics are governed by:

`docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md`

That domain spec is authoritative for accounting rules. This document only defines workspace ownership.

## 10. Administration Workspace

Purpose: system/user/role/permission/configuration/operational administration and platform-facing management workflows.

Administration may configure platform/business capabilities but should not contain duplicated domain business logic from Student, Teaching or Finance.

## 11. Domain ownership

Conceptually:

```text
Student Domain
Teaching/Class Domain
Employee/Teacher Domain
Finance Domain
Administration Domain
```

Each business concept has one owner. Cross-domain communication should occur through application services, DTO/read models or events rather than direct UI-to-UI mutation or copied rules.

## 12. UI architecture

UI code is workspace-oriented. The UI:

- renders application/domain state;
- invokes services;
- projects capabilities and domain state;
- coordinates navigation/refresh.

UI must not become an alternate domain layer.

Do not put canonical accounting, enrollment, authorization or persistence rules into widgets/views merely because a control needs to reflect them.

## 13. Service architecture

Services are application/domain use-case boundaries. They may be shared across workspaces when the underlying domain capability is genuinely shared.

The current implementation uses a mostly flat `services/` package. Domain ownership is semantic, not determined solely by folder nesting.

## 14. Repository architecture

Repositories own persistence/query mechanics. The current implementation uses a mostly flat `repositories/` package plus repository-provider patterns.

Repositories must not become product-workflow owners or UI helpers.

## 15. Platform architecture

Collaboration, synchronization, bootstrap, runtime context, notification/version and deployment concerns belong to the shared Platform layer (`src/centermanager/platform/`).

Business workspaces must not implement Git synchronization or edit-session protocols independently.

## 16. Workspace independence

Examples of forbidden ownership drift:

- Finance UI directly editing Student profile rules;
- Student UI implementing Session lifecycle;
- Teaching UI implementing Finance settlement/accounting;
- business services directly managing Git collaboration metadata.

Referencing another domain through an approved service/read model is allowed; duplicating ownership is not.

## 17. Dashboard philosophy

A workspace dashboard is a read/projection surface for that workspace's domain.

Dashboards do not define separate business semantics. For example, Finance Dashboard must consume the same canonical FinancePeriod and ledger semantics as Income, Expense, Outstanding and Settlement.

## 18. Reports and analytics

Reports are projections over authoritative domain data. They should remain read-oriented unless an explicit workflow owns a mutation.

A future dedicated Report Workspace is allowed, but reports must not create duplicate business-rule implementations.

## 19. Future expansion

Possible future workspaces/capabilities include CRM, marketing, inventory, library, parent portal, equipment and AI assistance.

New capabilities should attach to a clear business owner and reuse Platform infrastructure rather than causing cross-domain coupling.

## 20. Architecture principles

1. Home/Application Shell does not own domain workflows.
2. One business concept has one domain owner.
3. Workspaces own user workflow/presentation context, not arbitrary persistence.
4. UI calls services; services/repositories own domain/persistence boundaries.
5. Cross-domain behavior uses services/read models/events.
6. Shared platform infrastructure is not duplicated by business domains.
7. Conceptual workspace architecture and physical package layout are separate concerns.
8. Domain-specific approved specs override generic examples in this document.

## 21. Relationship to other documents

- `docs/ARCHITECTURE.md` — current implementation/layer architecture.
- `docs/Deployment_Docs/100_ARCHITECTURE_PRINCIPLES.md` — long-term platform principles.
- domain specs — authoritative detailed business contracts.
- GitHub Issues — task implementation contracts.
- root `AGENTS.md` — standing coding-agent workflow/rules.

## 22. Change policy

Architecture V2 remains the approved workspace/product direction, but it is not “frozen against reality”. When the implemented product intentionally evolves, this document must be updated through architecture review rather than left stale.

Breaking a domain ownership principle requires an explicit architecture decision; updating examples/package mappings to match the actual codebase does not.