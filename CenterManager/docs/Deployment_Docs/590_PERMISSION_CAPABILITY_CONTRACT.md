# 590_PERMISSION_CAPABILITY_CONTRACT.md

Version: 1.1
Status: ACTIVE
Document Type: Platform Security Contract
Owner: OpenAI & AnTechKids

Depends On

- 100_ARCHITECTURE_PRINCIPLES.md
- 200_COLLABORATIVE_ARCHITECTURE.md
- 300_WORKSPACE_MODEL.md
- 400_EDIT_SESSION_PROTOCOL.md
- 560_MODULE_MODEL.md
- 570_SHARED_KERNEL.md
- 575_PLATFORM_CONTRACT.md

---

## 1. Purpose

This document defines the single permission and capability vocabulary for CenterManager.

The contract separates three concepts:

- **Role** — who the actor is in the platform.
- **Capability** — what protected operation the actor may request.
- **Decision** — whether the request is allowed in its current context.

A role is not a capability.
A UI mode is not a capability.
An implementation method is not a capability.

Business and UI code must consume the capability contract instead of inventing local role/permission rules.

## 2. Canonical Vocabulary

### Role

A Role identifies an actor class used by authorization policy.

Canonical roles:

- `ADMIN`
- `MANAGER`
- `EMPLOYEE`

The runtime currently persists the employee actor class using the operational roles `teacher`, `reception`, and `finance`; these remain distinct role identifiers because they have different permission profiles. They are employee-scoped roles under the `EMPLOYEE` actor class and must not be silently renamed as part of capability normalization.

Role values are identifiers, not UI labels. Presentation layers may localize labels without changing the identifiers.

### Capability

A Capability is the stable identifier for one protected operation.

Capability identifiers use lowercase dot-separated namespaces:

```text
<domain>.<resource>.<operation>
```

The canonical runtime registry is:

```text
CenterManager/src/centermanager/core/capabilities.py
```

`Capability` is the source of truth for capability identifiers. The database `Permission` model stores these identifiers for role assignments; compatibility APIs such as `PermissionDefinitions` must alias the canonical values rather than define independent names.

Canonical capabilities currently established by the platform:

| Capability | Meaning | Default role policy |
|---|---|---|
| `work_registration.view.all` | View work registrations belonging to other employees | `MANAGER`, `ADMIN` |
| `work_registration.manage` | Perform ordinary operational work-registration management | Existing operational policy; role-specific rules remain owned by the EWR domain |
| `work_registration.period.admin_override` | Reopen a closed work-registration period | `ADMIN` |
| `work_registration.delete` | Delete a work-registration aggregate | `ADMIN` |
| `employee.delete` | Hard-delete an employee with no operational history | `ADMIN` |
| `class.teacher_assignment.manage` | Assign/unassign a teacher for a class | `ADMIN`, `MANAGER` |

The list above is the platform's canonical name registry. New capabilities must be added to the runtime registry before implementation code introduces a new identifier.

## 3. Authorization Decision

Authorization is evaluated as:

```text
Decision = Authorize(Actor, Capability, Context)
```

The decision has exactly two externally observable outcomes:

- `ALLOW`
- `DENY`

A denied operation must not mutate business state.

A caller must not infer authorization from a button state, workspace state, or exception type.

## 4. Context

Authorization context may contain:

- `actor_id`
- `roles`
- `capability`
- `workspace`
- `edit_session`
- `resource_id` when required by domain policy
- `platform_mode`

Context is request-scoped. It is not business data.

The authorization contract does not prescribe storage or authentication technology.

## 5. Role-to-Capability Policy

Role policy is additive and explicit.

```text
ADMIN   -> administrative capabilities + explicitly granted operational capabilities
MANAGER -> manager capabilities + explicitly granted operational capabilities
EMPLOYEE -> employee-scoped capabilities
```

The platform must not use role-name checks as a substitute for a capability check in application flows.

Example:

```text
BAD
if current_user.role == "Admin":
    allow_delete()

GOOD
if authorization.allows("employee.delete"):
    allow_delete()
```

A domain may impose additional resource or lifecycle constraints after capability authorization. Capability authorization alone does not bypass domain invariants.

## 6. Write Mode Is Context, Not Permission

`WRITE` / `READ` is a workspace or interaction state.
It is not a permission and must not be registered as a capability.

For a mutation, the effective rule is:

```text
Capability ALLOW
AND
Edit Session permits mutation
AND
Domain invariants pass
```

Therefore a user who has a capability can still be denied when no valid Edit Session exists, the target resource is not mutable, or another domain invariant fails.

This preserves the Edit Session contract, which explicitly replaces direct write permission with controlled editing sessions.

## 7. Administrative Capabilities

Administrative capabilities are explicit and auditable.

For the current EWR contract:

```text
work_registration.period.admin_override -> ADMIN only
work_registration.delete                 -> ADMIN only
employee.delete                          -> ADMIN only
```

An administrative override must never be inferred from generic write access.

The EWR domain remains responsible for required reasons, audit events, and aggregate-specific safety checks.

## 8. Authorization Boundaries

Authorization responsibilities are split as follows:

### Presentation

May ask whether a capability is allowed and reflect the answer in UI state.

Must not define policy.

### Application

Must enforce capability authorization before invoking a protected use case.

### Domain / Business

Owns business invariants and resource-specific rules.

Must not duplicate role-to-capability mappings.

### Collaboration Platform

Owns Edit Session and synchronization semantics.

A capability grant never creates or transfers an Edit Session.

### Infrastructure

May implement authentication or policy persistence behind an interface.

Infrastructure must not redefine capability semantics.

## 9. Failure Semantics

Authorization failures are represented as a permission error in the shared result/error model.

Canonical classification:

```text
PermissionDenied
```

A permission denial must be deterministic and must not partially apply the requested mutation.

Authentication failure and authorization denial are separate concerns.

## 10. Capability Naming Rules

Capability identifiers must be:

- stable;
- lowercase;
- dot-separated;
- action-oriented;
- independent of UI terminology;
- independent of implementation classes.

Forbidden examples:

```text
is_admin
can_write
write_mode
admin_button_enabled
EmployeeDeleteDialog
```

Preferred examples:

```text
employee.delete
work_registration.delete
work_registration.period.admin_override
```

## 11. Compatibility Rules

Capability identifiers are public platform contract values.

Therefore:

- renaming a capability is a breaking contract change;
- removing a capability is a breaking contract change;
- changing the meaning of an existing capability is a breaking contract change;
- adding a new capability is backward compatible;
- role policy may become stricter only through an explicit policy change and regression review.

Aliases may be temporarily supported during migration, but new code must use the canonical identifier.

## 12. Migration Rule

Existing code may still contain local role checks or legacy names.

Migration must converge toward:

```text
Role -> Capability -> Authorization Decision
```

Do not create parallel permission registries in individual modules or workspaces.

During migration, legacy checks must not silently diverge from the canonical capability registry.

The runtime migration is implemented through `AuthorizationService` and the compatibility `PermissionService` facade. `PermissionService` must delegate authorization decisions to `AuthorizationService`; it must not add a role-name bypass.

## 13. Contract Invariants

The following are mandatory:

1. Every protected operation has one canonical capability identifier.
2. A capability identifier has one semantic meaning.
3. Role names never replace capability identifiers in protected application flows.
4. UI state never acts as the authorization source of truth.
5. Authorization denial causes no business mutation.
6. Capability authorization does not bypass Edit Session rules.
7. Capability authorization does not bypass domain invariants.
8. Administrative overrides use explicit administrative capabilities.
9. Capability semantics are independent of deployment technology.
10. New capability identifiers are registered in one canonical contract.
11. The runtime registry and persistence permission names must not diverge.
12. Authorization decisions fail closed for inactive or role-less actors.

## 14. Reference Decision Flow

```text
User Action
    ↓
Application Use Case
    ↓
Authorization(Actor, Capability, Context)
    ↓
ALLOW ?
 ├── NO  → PermissionDenied → No Mutation
 └── YES
        ↓
   Edit Session / Lifecycle Checks
        ↓
   Domain Invariants
        ↓
   Business Mutation
```

## 15. Non-goals

This contract does not define:

- authentication protocols;
- password handling;
- identity-provider implementation;
- database schema for permissions;
- UI role management screens;
- concurrent editing policy;
- business invariants owned by individual domains.

Those concerns remain behind their existing architectural boundaries.

---

## Summary

CenterManager uses one normalized authorization language:

```text
Role
  ↓
Capability
  ↓
Authorization Decision
  ↓
Edit Session / Domain Checks
  ↓
Mutation
```

Permissions are stable platform contracts. Roles provide actor context. Workspace `READ/WRITE` state and Edit Session state are operational constraints, not permission identifiers.

This separation prevents permission logic from fragmenting across UI, modules, and infrastructure while preserving the existing collaboration and business boundaries.
