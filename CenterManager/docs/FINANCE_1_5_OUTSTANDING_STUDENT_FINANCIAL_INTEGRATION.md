# FINANCE-1.5 — Outstanding & Student Financial Integration

## Goal

Close the end-to-end financial contract:

Class fee -> Enrollment -> Expected tuition -> Tuition Income -> OutstandingService
-> Student Financial UI -> Finance Outstanding UI -> Finance Dashboard.

## Source of truth

`OutstandingService` owns tuition expected/paid/outstanding calculations.

`StudentFinancialWidget` and `OutstandingListPage` consume its DTOs. They do not
recalculate outstanding independently.

## Tuition integrity states

Per enrolled student/class pair:

- Paid: expected == paid
- Partial: expected > paid
- Overpaid: paid > expected
- No Tuition Configured: class fee is missing or zero

A missing tuition configuration never means a zero debt has been settled.

## Important payment rule

A real Tuition payment remains visible in the student's `total_paid` even when
the related class fee is not configured. Expected/debt math only uses configured
tuition amounts. This prevents collected money from disappearing from the
Student Financial screen.

## Multi-class safety

Outstanding aggregation deduplicates:

- student/class pairs in the Finance Outstanding list
- class IDs in the Student Financial summary

This prevents duplicate Enrollment rows from silently double-counting tuition.

## UI contract

Student Financial shows:

- total expected tuition
- total tuition paid
- outstanding balance
- overall status
- per-class expected/paid/outstanding/status
- tuition payment history

For unconfigured tuition, UI explicitly displays `Chưa cấu hình` /
`Chưa xác định` instead of `0`.

## Finance-1.5 boundary

No new manual debt editing is introduced. Class fee and Tuition Income remain
the authoritative inputs; outstanding is derived read-only.
