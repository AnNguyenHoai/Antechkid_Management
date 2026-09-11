# FINANCE-1.4 — Expense Lifecycle

## Lifecycle

`Create -> Read/List -> Update -> Soft Delete`

All mutations remain permission-protected:

- finance.expense.create
- finance.expense.update
- finance.expense.delete

## Canonical contracts

Payment method:

- Cash
- Bank

Legacy stored values remain readable and are normalized at the service boundary:

- TÀI KHOẢN CÁ NHÂN -> Cash
- TÀI KHOẢN CÔNG TY -> Bank
- Bank Transfer -> Bank

Status:

- Pending
- Completed

Legacy values remain readable:

- CHƯA HOÀN TRẢ -> Pending
- ĐÃ HOÀN TRẢ -> Completed

## Data integrity

- Category must be supported.
- Description is required.
- Amount must be numeric and greater than zero.
- Payment date is required and valid.
- Deleted records cannot be updated or deleted again.

## Audit

Create, update and delete create ExpenseTimeline events.

## UI safety

When WRITE is disabled, Add/Edit/Delete are disabled. Service permission checks remain mandatory.

## Scope

Dashboard and event-bus refresh are deferred to later Finance integration tasks.
