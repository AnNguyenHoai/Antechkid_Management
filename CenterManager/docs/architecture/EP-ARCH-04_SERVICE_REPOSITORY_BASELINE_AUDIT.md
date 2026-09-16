# EP-ARCH-04 — Full Service & Repository Architecture Baseline Audit

Baseline: `5bec3f0420f2ec515c564c2687d9a0bd258c2072`

## Scope

This audit is read-only at the production-code level. It establishes the architecture baseline after EP-ARCH-03 and Phase 2 hardening.

Audited areas:

- `CenterManager/src/centermanager/services/`
- `CenterManager/src/centermanager/repositories/`
- `CenterManager/tests/` architecture contracts
- `CenterManager/docs/architecture/` service-boundary inventory and dependency documentation

## Target architecture

```text
Application Service
        |
        v
RepositoryProvider
        |
        v
Concrete Repository
        |
        v
SQLAlchemy / Database
```

Application services may orchestrate business/application flow and transaction completion (`commit` / `rollback`), but database query construction and ORM persistence/state operations belong to repositories.

## Baseline findings

### 1. Service inventory is complete at the documentation level

`EP-ARCH-03_SERVICE_INVENTORY.md` classifies the current service tree into `PASS` and `NON_REPOSITORY` with no remaining `LEGACY` or `VIOLATION` rows. The inventory documents all completed EP-ARCH-03 migration slices through EP-ARCH-03.39 and the Phase 2 Student hardening slice.

Status: **DOCUMENTED**

### 2. RepositoryProvider coverage is broader than the service inventory alone proves

`RepositoryProvider` exposes repository seams for assessment, attendance, enrollment, sessions, session notes, employees, schedules, work-registration periods/records, working time, documents, classes, students, assessments, reports, expenses, income, teachers, teacher assignments/documents, notes, users/roles/permissions, parents, student highlights, finance periods, and timeline.

Status: **STRUCTURALLY COVERED**

### 3. Existing architecture tests are not yet a single global source-driven gate

The Phase 2 hardening test directly audits only:

- `student_export_service.py`
- `student_import_service.py`
- `student_note_service.py`

The EP-ARCH-03 documentation states that the final boundary audit is source-driven and dynamically discovers every `*_service.py`, but the current Phase 2 test file itself does not implement that global scan.

Status: **GAP — P0**

Required follow-up: create one authoritative AST-based global service boundary regression test which dynamically discovers the complete service tree and validates every service according to its declared classification.

### 4. Inventory contract is partly duplicated across separate tests

`test_ep_arch_03_34_inventory_contract.py` keeps an explicit expected PASS set, while `test_ep_arch_03_35_batch_g_non_repository_services.py` separately keeps explicit NON_REPOSITORY and migrated PASS sets.

This is useful as historical regression coverage, but it creates an allowlist-maintenance burden and can drift from the source tree.

Status: **GAP — P1**

Required follow-up: distinguish historical migration assertions from the authoritative live architecture gate. The live gate should derive the service set dynamically.

### 5. RepositoryProvider factory seam is centralized

The production provider is a `Protocol` plus `SqlAlchemyRepositoryProvider`. Concrete repositories are constructed behind the provider seam rather than by application services.

Status: **COMPLIANT BASELINE**

### 6. Transaction responsibility is intentionally still at service level

EP-ARCH-03 explicitly allows `session.commit()` and `session.rollback()` as application transaction orchestration. This is not yet a proof that transaction ownership is consistent across all services.

Status: **PENDING DEEP AUDIT — P1**

Required follow-up: EP-ARCH-05/06-style transaction audit should identify commit/rollback counts, partial-commit patterns, repository-side transaction calls, and exception-path rollback behavior.

### 7. Repository boundary needs a dedicated contract audit

The current architecture documentation proves the intended service-to-repository direction, but the baseline has not yet established a uniform repository API contract, transaction policy, refresh semantics, or repository-to-repository dependency rule.

Status: **GAP — P1**

Required follow-up: dedicated repository contract audit.

## Gap register

| ID | Area | Finding | Priority | Action |
|---|---|---|---|---|
| ARCH-04-001 | Global service gate | No single authoritative AST gate dynamically validates every service against the live boundary rules | P0 | Add global service-boundary architecture test |
| ARCH-04-002 | Inventory/testing | Live contract relies partly on explicit service allowlists | P1 | Keep historical assertions, add source-derived live contract |
| ARCH-04-003 | Transactions | Commit/rollback ownership has not been audited globally after service migration | P1 | Perform transaction ownership audit |
| ARCH-04-004 | Repository contract | Repository API/lifecycle/transaction conventions are not baselined as one contract | P1 | Audit repository layer |
| ARCH-04-005 | Provider completeness | Provider seam is centralized, but provider-to-repository coverage is not enforced by one architecture test | P1 | Add provider completeness contract |
| ARCH-04-006 | Documentation drift | Inventory baseline SHA still points to an older historical baseline while the audit itself is based on `5bec3f0...` | P2 | Normalize baseline metadata in a later documentation-only task |

## Baseline conclusion

The post-EP-ARCH-03 architecture has no documented remaining legacy service backlog and has a centralized RepositoryProvider seam. The main architecture risk is now **regression protection and contract drift**, not another immediate service migration.

The next implementation slice should therefore be **EP-ARCH-04.1 — Global AST Service Boundary Gate**, followed by repository-provider completeness and transaction-ownership audits.

## Non-goals for this baseline

- No production service migration.
- No repository refactor.
- No transaction-policy changes.
- No permission/capability redesign.
- No behavior changes.
