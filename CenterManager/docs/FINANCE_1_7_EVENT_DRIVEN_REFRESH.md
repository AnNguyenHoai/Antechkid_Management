# FINANCE-1.7 — Event-Driven Auto Refresh

## Goal

Finance read models refresh automatically after committed Income and Expense mutations.

## Event contract

`FinanceDataChanged(entity, action, record_id, student_id, class_id)`

Events are published only after database commit.

## Producers

IncomeService:

- created
- updated
- deleted

ExpenseService:

- created
- updated
- deleted

## Consumer

FinanceWorkspaceShell subscribes once to `FinanceDataChanged`.

Income changes refresh:

- Income List
- Outstanding List
- Finance Dashboard

Expense changes refresh:

- Expense List
- Finance Dashboard

## Data consistency

No finance UI page recalculates business data locally. Refresh invokes each page's
existing service-backed read model.

## Scope boundary

This task covers committed Income/Expense mutations inside the Finance workspace.
Class fee/enrollment changes are outside Finance-1.7 and remain a separate
cross-workspace integration concern.
