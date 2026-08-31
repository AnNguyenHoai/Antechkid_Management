# EMPLOYEE 1.2 — Access & Self-Service Foundation

## Contract

- Every newly created employee must be linked to exactly one login account.
- Admin and Manager can view all employees.
- Other roles can view only their own employee profile when linked to their authenticated account.
- Data-level authorization is enforced in `EmployeeService`, not only in the UI.
- Employees can update only safe self-service fields (`phone`, `email`, `address`) at this stage.
- Employment fields remain management-controlled.
- Employee account creation and employee profile creation are atomic.
- Manager cannot create Administrator or Manager accounts.
- Self-service workspace exposes `My Profile` and `Attendance`; working-time behavior is implemented in the later Working Time task.

## Permissions

- `employee.view.self`
- `employee.view.all`
- Existing employee CRUD permissions remain for management operations.

## Compatibility

The database keeps `employees.user_id` nullable for legacy records. New employees are rejected without an account. Existing unlinked records are visible to management and must be linked before self-service access is available.
