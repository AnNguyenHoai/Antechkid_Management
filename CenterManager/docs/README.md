# CenterManager Documentation Map

Updated: 2026-11-04 (TECH-003: archive cleanup)

This file explains which documents are authoritative for which questions. It exists to prevent stale or conceptual documents from being mistaken for current implementation truth.

## 0. Product management (repository root)

These files sit at the repository root and track product scope, priorities and acceptance. They do not replace the technical contracts below.

- `/BACKLOG.md` — prioritized backlog, task status and Product Owner acceptance;
- `/PRODUCT_CONTEXT.md` — product goals, users, constraints, PO-confirmed facts;
- `/ARCHITECTURE.md` — short management summary pointing here;
- `/DECISIONS.md` — product/engineering decisions;
- `/CHANGELOG.md` — verified change history since 2026-11-04.

`docs/PROJECT_CONTEXT.md` and `docs/CHANGELOG.md` are now pointer stubs; their Sprint 0.x content is in `archive/legacy/`.

## 1. Current implementation

Use these first when you need to understand how the repository works today:

- `ARCHITECTURE.md` — current implementation architecture and layer/platform boundaries;
- `DEVELOPMENT_GUIDE.md` — current developer setup/workflow;
- `DATABASE_DESIGN.md` — current database architecture/invariants;
- `DEPLOYMENT.md` — deployment/runtime mode behavior;
- `INSTALL.md` — end-user installation behavior;
- `TROUBLESHOOTING.md` — safe operational recovery guidance.

## 2. Product / workspace architecture

- `Bussiness/ARCHITECTURE_V2.md` — approved workspace/product/domain ownership architecture.

This is conceptual/product architecture. It is not a literal package-layout contract.

## 3. Platform / collaboration architecture

Under `Deployment_Docs/`:

- `000_PLATFORM_VISION.md` — long-term platform direction;
- `100_ARCHITECTURE_PRINCIPLES.md` — durable architecture principles;
- `200_COLLABORATIVE_ARCHITECTURE.md` — collaboration/platform responsibilities and current direction;
- `300_WORKSPACE_MODEL.md` — workspace ownership/presentation model;
- protocol-specific documents such as edit-session/synchronization specs — detailed platform behavior where still applicable.

High-level platform vision does not automatically override a more specific approved domain contract.

## 3a. Security, runtime and release operations

- `SECURITY_MEDIUM_PROFILE.md` — security baseline, deployment profiles, SQLCipher + DPAPI;
- `SEC_02_PROTECTED_DATA_SERVICE.md` — `AnTechKidsData` Windows service boundary;
- `GIT_AND_WINDOWS_RUNTIME_SECURITY_POLICY.md` — Git credentials and Windows runtime policy;
- `EP-SEC-01_DATABASE_LIFECYCLE_PROTECTION.md` — database lifecycle protection;
- `PRODUCTION_DATABASE_UPGRADE_GATE.md` — production database upgrade gate;
- `RELEASE_CHECKLIST.md`, `PORTABLE_UAT_A4_5.md`, `SEC06_ISOLATED_UAT.md`, `security/` — release and UAT procedures/evidence;
- `collaboration/` — WRITE authority, durable recovery and publication contracts;
- `qa/` — regression matrices and results;
- `incidents/` — incident reports.

## 3b. Documents pinned by tests

Some documents are read by regression tests at their current path and must not be moved or renamed without updating those tests: `PROTOTYPE_SCOPE.md`, `EP-PROTOTYPE-02…13_*.md`, `EP-PROD-05_*.md`, `EP-PROD-06_*.md`, `PHASE_2_PRODUCT_HARDENING.md`, `SEC06_ISOLATED_UAT.md`, `STUDENT_2_6_STUDENT_REPORT_DATA_CONTRACT_AUDIT.md`, `Deployment_Docs/`, `architecture/EP-ARCH-03_SERVICE_INVENTORY.md`, `finance/FINANCE_WALLET_V2_TUITION_BOUNDARY.md`, `ui_baseline/UI_PROD_*`.

## 4. Domain sources of truth

A domain-specific approved spec is authoritative for that domain.

Finance examples:

- `finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` — Finance Wallet V2 domain contract;
- `finance/FINANCE_WALLET_V2_SETTLEMENT_AUTHORIZATION.md` — approved R6 clarification defining Settlement capability identifiers, role grants, service enforcement and UI projection;
- `finance/FINANCE_WALLET_V2_IMPLEMENTATION_TRACKER.md` — progress/evidence only, not a replacement for the Domain Spec or an approved clarification contract.

When code/tests conflict with an approved domain spec because the spec intentionally changed behavior, the spec defines the target contract.

## 5. Task implementation contracts

GitHub Issues define the implementation scope for individual tasks:

- context/problem;
- scope/non-goals;
- acceptance criteria;
- required tests;
- base SHA/branch;
- Definition of Done.

Issues do not silently override approved domain contracts.

## 6. Coding-agent rules

Repository-root `AGENTS.md` defines standing rules for Codex/AI developers:

- branch discipline;
- architecture boundaries;
- testing;
- migration safety;
- PR/CI/review flow;
- stop conditions.

## 7. Historical implementation docs

Completed task/sprint implementation records (ADMIN_1_x, CLASS_x, EMPLOYEE_x, STUDENT_x, TEACHER_x, FINANCE_1_x, FINAL_HARDENING_x, EP-RELEASE-01, EP_ARCH_03, PR_F…PR_J, …) live in `archive/sprint-reports/`. Superseded design documents (old `FINANCE/`, `Software/`, Sprint 0.x context/changelog) live in `archive/legacy/`. Some historical records remain at the top level only because tests pin their paths (section 3b).

These files are useful evidence/history, but they should not automatically be treated as the current global architecture.

When a historical task document conflicts with:

1. an approved current domain spec or clarification;
2. `ARCHITECTURE.md` current implementation description;
3. current code/architecture gates;

use the newer authoritative source and preserve the old document as historical evidence. New task reports should go to `archive/sprint-reports/` once the task is merged, not to the top of `docs/`.

## 8. Documentation update rule

When implementation materially changes a documented contract:

- update the owning canonical document;
- update progress/evidence trackers where relevant;
- avoid creating another competing architecture document;
- mark conceptual/future behavior clearly;
- do not leave dangerous operational procedures in troubleshooting/deployment docs after runtime behavior changes.

## 9. Quick decision table

| Question | Read first |
|---|---|
| How does the codebase work today? | `ARCHITECTURE.md` |
| How should a developer work? | root `AGENTS.md` + `DEVELOPMENT_GUIDE.md` |
| What are workspace/domain ownership boundaries? | `Bussiness/ARCHITECTURE_V2.md` |
| How does collaboration/platform responsibility work? | `Deployment_Docs/200_COLLABORATIVE_ARCHITECTURE.md` |
| What is the long-term platform direction? | `Deployment_Docs/000_PLATFORM_VISION.md` |
| What is the exact database schema? | ORM models + Alembic migrations |
| What are Finance business rules? | `finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| What are Settlement authorization rules? | `finance/FINANCE_WALLET_V2_SETTLEMENT_AUTHORIZATION.md` |
| What is the next Finance task? | Finance tracker + assigned GitHub Issue |
| What should Codex implement? | assigned GitHub Issue + `AGENTS.md` |
| How should an end user recover from an error? | `TROUBLESHOOTING.md` |
| What is prioritized / accepted by the PO? | `/BACKLOG.md` + `/DECISIONS.md` |
| How is production data protected? | `SECURITY_MEDIUM_PROFILE.md` + `SEC_02_PROTECTED_DATA_SERVICE.md` |
