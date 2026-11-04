# EMPLOYEE 1.2-R — Profile & Account Model Correction

## Product contract
- User Account is the entry point for a new employee.
- Creating a new User automatically creates exactly one Employee profile in the same transaction.
- Employee Workspace does not create standalone employees.
- CV/Documents are managed inside Employee Profile.
- Admin and Manager can see all employee profiles.
- Other roles can only access their own profile.
- Self-service can edit personal profile fields only.
- Employment fields remain management-controlled.

## Compatibility
Legacy users/employees are supported. `EmployeeService.get_current_employee()` lazily repairs a missing legacy Employee profile when the authenticated account first enters Employee Workspace.
