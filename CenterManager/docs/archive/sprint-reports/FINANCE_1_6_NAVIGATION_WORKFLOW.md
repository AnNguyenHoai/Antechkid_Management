# FINANCE-1.6 — Finance Navigation & Workflow Integration

## Goal

Close the navigation loop between Finance Dashboard, Income, Expense,
Outstanding, and Student Financial workflows.

## Workflow contract

Finance Dashboard:
- Income -> Income list/detail
- Expense -> Expense list/detail
- Outstanding -> Outstanding list

Recent transaction rows:
- double-click recent income -> Income detail
- double-click recent expense -> Expense detail

Outstanding:
- double-click student/class debt row -> Student Workspace detail

## Boundary

The Finance workspace does not duplicate Student Detail. It emits the selected
student ID and MainWindow owns the cross-workspace navigation.

## Single responsibility

- Dashboard emits navigation intent
- FinanceWorkspaceShell routes finance-internal workflows
- MainWindow routes cross-workspace workflows
- Existing detail dialogs remain the record-detail source of truth
