# CenterManager Documentation Map

Updated: 2026-09-24

This file explains which documents are authoritative for which questions. It exists to prevent stale or conceptual documents from being mistaken for current implementation truth.

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

## 4. Domain sources of truth

A domain-specific approved spec is authoritative for that domain.

Example:

- `finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` — Finance Wallet V2 domain contract;
- `finance/FINANCE_WALLET_V2_IMPLEMENTATION_TRACKER.md` — progress/evidence only, not a replacement for the Domain Spec.

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

Many files under `docs/` are task/sprint implementation records such as `*_FOUNDATION_*`, `*_HARDENING_*`, feature-specific contracts and prior audits.

These files are useful evidence/history, but they should not automatically be treated as the current global architecture.

When a historical task document conflicts with:

1. an approved current domain spec;
2. `ARCHITECTURE.md` current implementation description;
3. current code/architecture gates;

use the newer authoritative source and preserve the old document as historical evidence unless an explicit cleanup task says otherwise.

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
| What is the next Finance task? | Finance tracker + assigned GitHub Issue |
| What should Codex implement? | assigned GitHub Issue + `AGENTS.md` |
| How should an end user recover from an error? | `TROUBLESHOOTING.md` |
