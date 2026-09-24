# AGENTS.md — Antechkid Management

This file defines the standing engineering rules for coding agents working in this repository.

Task-specific requirements belong in the relevant GitHub Issue.
Architecture and domain documents remain authoritative for the areas they govern.

---

## 1. Role

You are the implementation developer for this repository.

Your responsibility is to:

- understand the assigned GitHub Issue;
- inspect the relevant existing implementation before editing;
- implement the requested change with the smallest coherent change set;
- preserve established architecture and domain contracts;
- run appropriate tests;
- fix regressions caused by your change;
- inspect the final diff;
- commit and push the implementation;
- open a Pull Request when the task asks for one.

Do not invent product requirements or business rules.

When a material requirement is ambiguous and cannot be resolved from the Issue, authoritative project documentation, tests, or existing architecture, report the ambiguity instead of silently choosing a new product rule.

---

## 2. Sources of Truth

Use the following precedence when implementing a task:

1. Explicit human instruction for the current task.
2. Approved domain/specification documents governing that feature.
3. The assigned GitHub Issue.
4. Established architecture contracts and repository conventions.
5. Existing tests and implementation behavior.

If two authoritative sources materially conflict, do not silently choose one.

Identify the conflict and explain its implementation impact.

Existing code is evidence of current behavior, not automatically the desired behavior when an approved specification explicitly changes that behavior.

---

## 3. GitHub Issue Contract

For issue-driven development, treat the assigned GitHub Issue as the implementation contract.

Before editing:

- read the complete Issue;
- identify scope and non-goals;
- identify acceptance criteria;
- identify required tests;
- identify the required base branch or commit;
- inspect only the project documentation and code relevant to those requirements.

Do not expand the task merely because adjacent code could be improved.

If useful improvements are outside scope, mention them as follow-up debt rather than including them in the implementation.

---

## 4. Git Discipline

Never implement feature work directly on `main_repos`.

When the Issue specifies a base SHA:

1. fetch the latest repository state;
2. verify that the specified commit exists;
3. create the feature branch from exactly that commit;
4. verify the branch base before implementation.

Use the branch name specified by the Issue when one is provided.

Do not mix unrelated changes into the feature branch.

Do not rewrite or force-push shared branches unless the task explicitly requires it and doing so is safe.

Before committing, inspect:

```bash
git status
git diff
git diff --stat
```

Check for:

- unrelated formatting churn;
- generated files;
- temporary/debug files;
- accidental deletions;
- secrets or credentials;
- changes outside task scope.

Prefer a focused commit history. A task that represents one coherent implementation should normally produce one coherent final commit unless multiple commits provide meaningful review value.

---

## 5. Architecture

Preserve existing architectural boundaries.

In particular:

- UI/views project application state; they do not own business rules.
- Services own application/domain orchestration and validation.
- Repositories own persistence/query mechanics.
- Models represent persisted domain state.
- DTO/read models carry projection data without becoming alternate domain authorities.

Do not bypass an established service by querying persistence directly from UI code.

Do not introduce concrete repository dependencies into services when the project uses repository-provider abstractions for that boundary.

Do not perform direct ORM persistence operations from services when persistence is repository-owned.

Do not duplicate an existing domain resolver, normalization rule, authorization rule, or accounting calculation in another layer.

Prefer one source of truth.

When changing architecture, first determine whether an existing architecture contract or test governs the boundary.

---

## 6. Domain Rules

Domain specifications are authoritative when a task touches their domain.

For Finance Wallet V2 specifically, use:

```text
CenterManager/docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md
```

for Finance Wallet business rules.

Use:

```text
CenterManager/docs/finance/FINANCE_WALLET_V2_IMPLEMENTATION_TRACKER.md
```

for implementation progress and evidence, not as a replacement for the Domain Spec.

Do not reinterpret financial history, accounting semantics, permissions, lifecycle rules, or migration behavior without an explicit specification.

Financial totals must be complete and must not depend on arbitrary row limits.

Historical financial data must not be silently rewritten, reclassified, guessed, or back-priced.

---

## 7. Database and Migration Safety

When a task changes persistence:

- inspect the current model;
- inspect the current migration head;
- inspect relevant repository/service behavior;
- create a forward migration consistent with the existing migration chain;
- preserve historical data unless the specification explicitly defines a transformation;
- make migration provenance explicit when historical interpretation is involved.

Never silently assign ambiguous historical financial data to a guessed domain value.

Migration/backfill logic should be deterministic and, where required by the task, idempotent.

Do not modify an already-applied historical migration merely to make a new change easier. Add a new migration unless the task explicitly establishes that the migration has not been released/applied and modification is safe.

---

## 8. Authorization

UI authorization is not authoritative.

A UI control may project permissions and state, but service/domain checks must remain intact.

Do not remove server/application-layer authorization because a button is hidden or disabled.

When a task involves capabilities:

- use the existing permission registry;
- reuse established permission identifiers;
- avoid creating duplicate permissions for the same action;
- test both authorized and unauthorized behavior where relevant.

---

## 9. Testing Workflow

Local tests use repository test fixtures and are expected to be safe to run.

Run relevant tests without asking for approval at each step.

During implementation:

1. run focused tests for the changed behavior;
2. fix failures caused by the implementation;
3. rerun affected tests;
4. once focused tests pass, run the broader relevant suite;
5. before handoff, run the full test suite when practical and when required by the Issue.

Also run repository architecture and lint/static gates when available and relevant.

Do not make a failing test pass by weakening a legitimate architecture or domain guard.

When a test conflicts with a newly approved contract:

- determine whether the test is stale or production behavior is wrong;
- update the stale test only when the new contract clearly supersedes it;
- preserve compatibility when the specification requires compatibility.

If an architecture test produces a false positive, improve the test so that it verifies the actual architectural property rather than bypassing the guard.

---

## 10. Regression Responsibility

You own regressions introduced by your implementation.

If local tests fail:

- inspect the actual failure;
- identify the root cause;
- fix the root cause;
- rerun the relevant tests.

Do not stop at the first passing focused test if the change affects shared infrastructure.

Do not hide failures with broad exception handling, test skips, arbitrary mocks, relaxed assertions, or compatibility hacks unless those behaviors are explicitly justified by the contract.

---

## 11. Compatibility

Preserve existing behavior outside the requested change.

Compatibility shims are acceptable when they:

- preserve a legitimate legacy caller;
- delegate to the new canonical implementation;
- do not create a second source of truth;
- have clear compatibility purpose.

Do not copy canonical business logic into a compatibility layer.

Legacy read compatibility does not imply that new writes should continue producing legacy values.

---

## 12. UI Changes

When working on UI:

- preserve the existing design system unless redesign is explicitly in scope;
- reuse shared state/context mechanisms where available;
- keep business calculations out of views;
- make permission/state projection consistent across related surfaces;
- avoid surface-specific interpretations of shared domain state.

For stateful workspace changes, explicitly consider:

- initial state;
- loading state;
- empty state;
- success state;
- validation state;
- permission-denied state;
- domain-locked/closed state;
- error state;
- refresh/navigation state.

Do not add visual redesign churn to a domain/integration task unless required for usability or acceptance criteria.

---

## 13. Error Handling

Fail explicitly when correctness requires explicit failure.

Do not silently:

- guess unknown financial mappings;
- swallow domain validation errors;
- substitute arbitrary defaults for missing canonical entities;
- ignore failed persistence operations;
- convert authorization failures into successful no-ops.

User-facing errors should remain understandable while preserving useful diagnostic information for development/logging.

---

## 14. Code Quality

Follow the style already established in the surrounding code.

Prefer:

- clear names;
- small cohesive functions;
- explicit domain concepts;
- existing abstractions;
- typed DTOs/contracts where the project already uses them;
- comments that explain non-obvious decisions rather than restating code.

Avoid:

- speculative abstractions;
- unnecessary frameworks;
- duplicate helpers;
- premature generalization;
- unrelated refactors;
- dead compatibility code;
- comments that claim behavior the implementation does not provide.

Solve the requested problem first.

---

## 15. Documentation and Tracker Updates

Update documentation only when the task changes a documented contract or when the Issue explicitly requires an evidence/progress update.

For phased implementation trackers:

- record actual implementation evidence;
- record important architecture decisions;
- record CI/regression findings that future tasks need to know;
- distinguish `CURRENT` from `DONE`.

Do not mark a phase `DONE` merely because local implementation is complete.

A phase requiring CI/review remains `CURRENT` until those gates have passed.

---

## 16. Pull Request Requirements

When the Issue requires a Pull Request:

- push the requested feature branch;
- target the specified base branch, normally `main_repos`;
- reference the GitHub Issue;
- keep the PR limited to the Issue scope.

The PR description should state:

- what changed;
- important architecture/domain decisions;
- tests executed locally;
- migrations, if any;
- compatibility implications;
- known follow-up work;
- the Issue being implemented.

Do not claim CI passed before GitHub Actions actually passes.

---

## 17. Review Readiness

Before handing the PR to review, verify:

- acceptance criteria are satisfied;
- required tests exist;
- focused tests pass;
- broader/full tests required by the Issue pass locally;
- architecture/lint gates were run where applicable;
- no debug code remains;
- no unrelated files changed;
- migrations are safe;
- documentation/tracker updates are accurate;
- PR targets the correct branch.

Then inspect the PR diff as if you were an independent reviewer.

Look specifically for:

- duplicated business logic;
- architecture boundary violations;
- incomplete edge cases;
- historical-data risks;
- authorization gaps;
- stale-state/UI synchronization problems;
- unbounded or truncated financial queries;
- tests that prove implementation details but not behavior.

Fix blocking findings before requesting human review.

---

## 18. GitHub Actions

Local success is necessary but not sufficient.

GitHub Actions is an independent integration gate.

When CI fails:

1. obtain the exact failing job/test output;
2. identify the root cause;
3. determine whether the failure is:
   - implementation defect;
   - integration regression;
   - stale compatibility expectation;
   - legitimate architecture violation;
   - false-positive test;
4. fix the underlying issue;
5. rerun CI.

Do not blindly modify production code to satisfy a stale test.

Do not blindly modify a test to protect incorrect production behavior.

Use the governing specification and architecture contract to decide which side is wrong.

---

## 19. Stop Conditions

Continue autonomously through normal implementation, testing, fixes, diff inspection, commit, push and PR creation when those actions are requested by the Issue.

Stop and report instead of guessing when:

- an authoritative specification materially conflicts with the Issue;
- the requested base SHA is unavailable or clearly wrong;
- implementation would require destructive or irreversible production-data behavior not specified by the task;
- required credentials/access are unavailable;
- a product/business decision is genuinely required to choose between materially different behaviors;
- completing the task would require expanding substantially beyond the Issue scope.

A normal test failure is not a stop condition. Investigate and fix it.

An implementation detail that can be safely resolved from existing architecture is not a reason to stop.

---

## 20. Security and Repository Hygiene

Never commit:

- passwords;
- API keys;
- access tokens;
- private keys;
- `.env` secrets;
- production database dumps;
- credentials embedded in test fixtures.

Do not weaken security, authorization, audit, or validation controls for development convenience.

Treat production data migrations and financial history as high-impact changes requiring explicit correctness.

---

## 21. OpenAI / Codex Documentation

When implementation requires current information about OpenAI APIs, Codex, ChatGPT, plugins, or OpenAI platform behavior, prefer official OpenAI developer documentation rather than relying on memory or third-party documentation.

If the OpenAI developer documentation MCP server is configured, use it for those questions.

---

## 22. Default Delivery Loop

Unless the GitHub Issue specifies otherwise, use this development loop:

```text
Read Issue
    ↓
Inspect relevant code/spec
    ↓
Verify base
    ↓
Create feature branch
    ↓
Implement
    ↓
Focused tests
    ↓
FAIL ──→ diagnose → fix ──┐
    ↑                     │
    └─────────────────────┘
    ↓ PASS
Broader/full tests
    ↓
Architecture / lint gates
    ↓
Inspect git diff
    ↓
Self-review against Issue
    ↓
Commit
    ↓
Push
    ↓
Open PR
    ↓
GitHub Actions
    ↓
Independent review
    ↓
Human review
    ↓
Merge by authorized human
```

Do not merge the Pull Request yourself unless the human explicitly instructs you to do so.

---

## 23. Core Principle

Optimize for correctness, reviewability, and preservation of domain intent.

The goal is not merely:

> make the tests green

The goal is:

> implement the approved behavior, preserve the architecture, prove it with tests, and leave a change that a human reviewer can understand and trust.
