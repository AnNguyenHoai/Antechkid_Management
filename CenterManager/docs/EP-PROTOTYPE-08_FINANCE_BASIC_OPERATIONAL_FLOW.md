# EP-PROTOTYPE-08 — Finance Basic Operational Flow

## Purpose
Freeze the P8 Finance Basic prototype contract defined by EP-PROTOTYPE-01 using the existing Finance Workspace and existing finance services.

## Operational flow
```text
Open Finance
  ↓
Dashboard / Balance view
  ↓
Income
  ↓
Expense
  ↓
Balance / cash-flow summary
```

## Required scope
- Finance Workspace is the entry point for the finance prototype.
- Income records are viewable through the existing Income page.
- Expense records are viewable through the existing Expense page.
- The dashboard provides finance summary information including revenue, expense and net cash flow.
- Cash/bank information is represented by the existing payment-method and finance dashboard data; this task does not introduce a new accounting model.
- Outstanding remains available as an existing read-only finance surface but is not expanded by this prototype task.

## Boundary contract
- Finance Workspace owns finance navigation only.
- Finance business persistence remains in existing finance services.
- UI pages do not create repositories or sessions.
- Finance access remains protected by the existing `finance.view` permission boundary.
- No second finance router, workspace service, repository abstraction, accounting engine, or event architecture is introduced.

## Completion gate
- Targeted EP-PROTOTYPE-08 tests pass.
- Existing regression suite remains green.
- No unrelated production behavior is changed.
