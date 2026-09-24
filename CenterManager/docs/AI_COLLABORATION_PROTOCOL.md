# ChatGPT ↔ Codex Collaboration Protocol

Status: ACTIVE
Updated: 2026-09-24

This document defines the shared communication channel between Product/Architecture (human + ChatGPT) and Developer/Reviewer agents (Codex).

The goal is to remove manual copy/paste of technical context. GitHub is the shared durable communication surface.

## 1. Communication surfaces

### Before a Pull Request exists

The assigned GitHub Issue is the canonical communication thread.

Use the Issue for:

- task/spec clarification;
- architecture decisions;
- product decisions;
- Codex blockers;
- scope clarifications;
- base SHA corrections;
- implementation status before PR creation.

Codex MUST read the Issue body and all newer Issue comments before starting or resuming implementation.

### After a Pull Request exists

The Pull Request becomes the canonical implementation/review thread.

Use the PR for:

- implementation summary;
- CI failures and fixes;
- architecture review findings;
- requested changes;
- Codex responses to review;
- readiness for human review.

The linked Issue remains the task contract. The PR thread is the execution/review conversation.

## 2. Message prefixes

Use these exact prefixes so humans and agents can quickly identify message intent.

### Product / Architecture → Codex

`[ARCHITECTURE DECISION]`

A binding clarification or architecture/product decision that resolves an ambiguity.

`[SPEC UPDATE]`

The Issue/domain contract changed. Codex must reread the referenced source before continuing.

`[REVIEW BLOCKER]`

A blocking review finding. Codex must fix it before the PR is ready for human review.

`[REVIEW NOTE]`

A non-blocking observation or follow-up debt.

`[REVIEW PASS]`

Architecture/Product review found no blocking issue at the reviewed revision.

### Codex → Product / Architecture

`[CODEX BLOCKER]`

Codex cannot safely continue because a real product/architecture decision is required.

A blocker comment must contain:

- the conflicting sources or behavior;
- relevant files/symbols;
- the materially different choices;
- implementation impact of each choice;
- confirmation that no speculative implementation was made.

`[CODEX STATUS]`

Short progress/update message when useful.

`[CODEX CI AUDIT]`

CI failure analysis with exact failing jobs/tests and root cause classification.

`[CODEX READY]`

Implementation is ready for review. Include:

- branch;
- head SHA;
- PR number/link;
- tests run locally;
- CI state;
- known follow-up debt.

`[CODEX RESPONSE]`

Response to a review finding, including what changed and where.

## 3. Source precedence

Communication comments do not replace governing sources.

Use this precedence:

1. explicit current human instruction;
2. approved domain/specification documents;
3. binding `[ARCHITECTURE DECISION]` / `[SPEC UPDATE]` comments for the assigned task;
4. GitHub Issue body;
5. repository architecture contracts and `AGENTS.md`;
6. current implementation/tests as evidence of existing behavior.

When a binding decision changes a durable domain rule, the owning canonical document should also be updated. Do not leave important product rules only in comments.

## 4. Resume protocol

When the human tells Codex to continue an existing Issue, Codex should need only the Issue number.

Example trigger:

```text
Continue Issue #340.
Read AGENTS.md and the complete Issue conversation first, then continue from the latest binding decision.
```

Codex must then:

1. fetch/read the Issue body;
2. read all Issue comments in chronological order;
3. identify the latest binding architecture/spec decision;
4. verify the required base/head state;
5. continue without asking the human to copy previous technical messages.

If a PR already exists, Codex must also read the full PR conversation and current diff/CI state.

## 5. ChatGPT review protocol

When the human asks ChatGPT to handle a blocker or review a task, the human should only need to provide the Issue or PR number.

Examples:

```text
Handle the Codex blocker on Issue #340.
```

```text
Audit PR #341 against its linked Issue.
```

ChatGPT should retrieve the Issue/PR conversation directly, make or document the required decision, and post the result back to GitHub.

The human does not need to relay technical details between agents.

## 6. Transition from Issue to PR

When Codex opens a PR:

- the PR must reference/close the assigned Issue as appropriate;
- Codex posts `[CODEX READY]` on the PR or Issue with the PR number;
- implementation/CI/review conversation moves to the PR;
- product/domain contract changes still belong in the Issue/canonical docs and should be linked from the PR.

## 7. Blocking rule

Codex may stop only for the stop conditions defined in `AGENTS.md`.

When stopping for a product/architecture ambiguity, Codex MUST post a `[CODEX BLOCKER]` comment to the assigned Issue before returning control to the human, whenever GitHub access is available.

Do not require the human to manually transfer the blocker text to ChatGPT.

If GitHub write access is unavailable, Codex may print the blocker locally as a fallback.

## 8. CI communication

CI status itself remains authoritative in GitHub Actions.

When CI fails, Codex should inspect the actual job/test output and post `[CODEX CI AUDIT]` to the PR when the root cause is non-trivial or requires a decision.

Normal implementation defects should be fixed autonomously without waiting for Product/Architecture.

If CI exposes a product/architecture conflict, post `[CODEX BLOCKER]` instead.

## 9. Review loop

The expected loop after PR creation is:

```text
Codex implementation
    ↓
GitHub Actions
    ↓
Codex self-review
    ↓
[CODEX READY]
    ↓
ChatGPT/Product architecture review
    ↓
[REVIEW BLOCKER] ──→ Codex fix ──→ tests/CI ──┐
    ↑                                         │
    └─────────────────────────────────────────┘
    ↓
[REVIEW PASS]
    ↓
Human review
    ↓
Human merge
```

## 10. Human trigger vocabulary

The normal human interaction should stay short.

Recommended triggers:

- `Start Issue #340.`
- `Continue Issue #340.`
- `Handle blocker on Issue #340.`
- `Audit PR #341.`
- `Continue after review on PR #341.`
- `CI failed on PR #341; audit/fix.`

All technical context should be recovered from GitHub and repository documentation rather than copied through the human.

## 11. Core principle

GitHub is the shared durable memory between ChatGPT, Codex and the human reviewer.

The human coordinates the workflow; the human should not have to act as a clipboard between agents.
