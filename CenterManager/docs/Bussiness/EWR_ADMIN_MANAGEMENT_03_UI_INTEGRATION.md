# EWR-ADMIN-MANAGEMENT-03 — Admin Employee & Registration UI Integration

## Purpose

Expose the existing administrator-only Employee Work Registration management boundary in Employee Workspace and make registration-period state explicit in the UI.

## Rules

- Only ADMIN can delete an Employee from Employee Workspace.
- Deleting an Employee requires a reason and confirmation.
- The existing backend safety rule remains authoritative: an Employee with operational history cannot be hard-deleted.
- Only ADMIN can reopen a CLOSED registration month from Employee Workspace.
- Reopening requires a reason and confirmation and records the existing administrative audit action.
- Reopening changes the period from CLOSED to OPEN; it does not rewrite Registration.status.
- Registration DRAFT + Period CLOSED is a valid state combination whose effective editability is locked.
- Once the period is reopened, a DRAFT registration can be edited through the registration detail page.

## Manual acceptance

1. Log in as ADMIN.
2. Open Employee Workspace → Employees, select an employee, and use **Delete Employee**.
3. Open Employee Workspace → Work Registrations and select a CLOSED month.
4. Use **Re-open Closed Month**, enter a reason, and confirm.
5. Verify the month becomes OPEN while each registration keeps its existing workflow state.
6. Open a DRAFT registration, select an availability block, and verify **Edit Selected** is enabled and persists changes.
7. Verify the edit/delete controls are disabled while the period is CLOSED.
