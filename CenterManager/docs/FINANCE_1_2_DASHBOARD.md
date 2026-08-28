# FINANCE-1.2 — Finance Dashboard

## Goal

Finance Dashboard is a read-only aggregation boundary. UI receives one coherent
dashboard contract instead of independently recalculating finance data.

## KPIs

- Revenue today / month
- Expense today / month
- Net monthly cash flow
- Net cash movement this month
- Net bank movement this month
- Total outstanding
- Number of students with debt
- Number of enrollment balances with tuition not configured

## Payment method normalization

Incoming labels are normalized to:

- Cash
- Bank
- Other

This makes dashboard aggregation resilient to existing values such as
`Bank Transfer`, `bank`, `Cash`, and Vietnamese labels.

## Important accounting scope

The dashboard reports **period cash flow**, not an accounting opening/closing
bank balance. No opening-balance model is introduced in Finance-1.2.

Outstanding comes only from `OutstandingService`, which is the Finance-1.1
source of truth.
