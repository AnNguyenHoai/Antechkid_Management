# CenterManager — Architecture Principles

Version: 1.1  
Status: **APPROVED PLATFORM PRINCIPLES**  
Updated: 2026-09-24

Depends on: `000_PLATFORM_VISION.md`

This document defines durable architecture principles. It is intentionally more stable than implementation documentation. For current code/package reality, use `docs/ARCHITECTURE.md`.

## 1. Purpose

CenterManager should remain understandable and evolvable as product scope, deployment, collaboration and infrastructure change.

Architecture exists to preserve business meaning while allowing implementation technology to evolve.

## 2. Architectural values

Prefer:

- stability over novelty;
- predictability over cleverness;
- maintainability over convenience;
- explicit business semantics over hidden technical behavior;
- reviewable changes over broad speculative refactors.

## 3. Separation of concerns

CenterManager separates these concerns conceptually:

```text
Presentation / Workspace UI
        ↓
Application Services / Policies / Read Models
        ↓
Persistence Abstractions / Repositories
        ↓
Database / Storage Implementations

Shared Platform capabilities:
Bootstrap · Authentication/Authorization · Collaboration
Synchronization · Runtime Context · Events · Notifications
```

This is a dependency/ownership model, not a requirement that every concept live in a separately nested package.

## 4. Dependency rules

### UI

UI must not bypass application/service boundaries for business mutations or ORM persistence.

### Application/services

Services own use-case/domain orchestration and validation. Where a repository/provider boundary exists, services depend on that boundary rather than concrete persistence mechanics.

### Repositories/persistence

Repositories own query and persistence mechanics and may depend on SQLAlchemy/database infrastructure.

### Platform

Platform owns runtime/bootstrap/collaboration/synchronization infrastructure. Business modules consume platform state/capabilities; they do not implement Git synchronization/edit-session protocols themselves.

Dependencies do not have to pass through an artificial “immediate neighbor” when an established shared abstraction (for example EventBus, Clock, current-user context or platform interface) is explicitly designed for cross-cutting use.

The invariant is **clear ownership and no business-rule duplication**, not mechanical folder adjacency.

## 5. Domain ownership

Each business concept has one authoritative owner.

Examples:

- Student profile/history → Student domain;
- Class/session/attendance → Teaching/Class domain;
- employee/teacher lifecycle → Employee/Teacher domain;
- accounting/Income/Expense/Settlement → Finance domain;
- identity/role/permission administration → Administration/Authorization domain.

Cross-domain behavior uses services, DTO/read models or events. It must not be implemented by copying another domain's rules.

## 6. Business semantics vs infrastructure

Business language must not depend on deployment details.

Business services should not express concepts such as Git branches, synchronization locks or filesystem paths unless that technical concept is itself the explicit application concern of the service.

Conversely, infrastructure/platform code must not invent business accounting, enrollment or authorization rules.

## 7. Collaboration and synchronization

Collaboration/synchronization is a Platform capability.

Business modules must not directly:

- run Git commands for business workflows;
- manage synchronization metadata;
- implement edit-session ownership;
- decide stale-vs-authoritative database behavior independently.

Configured Git synchronization may be authoritative for runtime data lifecycle, but that authority is implemented by Platform/bootstrap, not Finance/Student/Class services.

## 8. Authorization

Authorization is defense in depth:

```text
UI projection
AND
application/service capability enforcement
AND
applicable domain-state guards
```

UI visibility/enabled state improves UX but is never the sole security/domain boundary.

WRITE/edit-session ownership is not equivalent to permission.

## 9. Events

Events support decoupled projections, refresh and cross-feature reactions.

Events must not replace atomic persistence where correctness requires one transaction.

A critical transaction should commit first; non-critical post-commit projection/event work must not convert a committed operation into a false failure.

## 10. Persistence principles

- Schema evolution uses Alembic.
- Historical/domain data is preserved according to its owning lifecycle.
- Ambiguous historical financial data is never guessed silently.
- Persistence side effects should be explicit and reviewable.
- Database aggregation is preferred over arbitrary row-cap loading for complete totals.
- Domain history/effective-dated values are stored when current values would otherwise rewrite historical meaning.

## 11. Replaceability

Infrastructure should be replaceable without rewriting business semantics.

This does not mean every implementation must be abstracted preemptively. Introduce an abstraction when a stable boundary already exists or a concrete task requires replaceability/testing.

Avoid speculative adapter layers with no present architectural value.

## 12. Extension rules

Prefer extension with clear ownership over modification that spreads one concern across many domains.

However, “open for extension, closed for modification” is not a ban on changing existing code. Correctly evolving an existing owner is preferable to creating a parallel abstraction merely to avoid modification.

## 13. Architectural invariants

The following should remain true:

- UI does not own canonical business rules or ORM persistence.
- Business concepts have one authoritative owner.
- Services do not duplicate persistence/query mechanics already owned by repositories.
- Business domains do not implement synchronization infrastructure.
- Platform infrastructure does not redefine business semantics.
- authorization remains enforced below UI projection;
- domain-specific approved specs remain authoritative for their domain;
- historical financial meaning is not silently rewritten;
- architecture tests should verify actual dependencies/behavior, not fragile text patterns.

## 14. Anti-patterns

Treat these as architecture debt:

- UI issuing SQLAlchemy queries;
- service importing concrete repositories where provider abstraction is required;
- business service directly managing Git collaboration state;
- duplicated canonical resolver/normalizer logic;
- authorization enforced only by hidden/disabled buttons;
- arbitrary row limits used to compute financial totals;
- ORM hooks creating hidden application side effects;
- one domain mutating another domain through UI internals;
- stale documentation presented as current implementation truth;
- tests that enforce comments/string spelling instead of the actual architectural property.

## 15. Architecture review checklist

For a significant change ask:

1. Which domain owns the behavior?
2. Is the change reusing the existing authoritative rule or creating another one?
3. Is UI merely projecting state or becoming a business layer?
4. Does persistence remain repository-owned where that boundary exists?
5. Are authorization and domain-state guards still authoritative below UI?
6. Does the change preserve historical data semantics?
7. Does Platform remain the owner of synchronization/collaboration?
8. Are new abstractions justified by the task rather than speculation?
9. Are tests proving the intended behavior/boundary?
10. Do affected architecture/domain docs still describe reality?

## 16. Documentation roles

- `docs/ARCHITECTURE.md` — current implementation architecture.
- `docs/Bussiness/ARCHITECTURE_V2.md` — workspace/product/domain ownership architecture.
- this document — durable platform principles.
- `docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` and other approved domain specs — detailed domain truth.
- GitHub Issues — implementation contract for one task.
- root `AGENTS.md` — standing coding-agent execution rules.

## 17. Final principle

Architecture is the organization of change.

A good CenterManager architecture should let the product add or revise capabilities without creating duplicate business truths, hidden persistence behavior or infrastructure leakage into domain code.