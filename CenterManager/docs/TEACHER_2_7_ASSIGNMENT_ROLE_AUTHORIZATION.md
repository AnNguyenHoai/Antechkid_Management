# TEACHER-2.7 — Assignment Role Authorization

## Requirement

Only `admin` and `manager` accounts may assign or unassign classes for teachers.

## Enforcement

### Teacher Detail

`Manage Classes` is disabled for every role except:

- Administrator
- Manager

The action handler also performs a runtime role check.

### Assignment Dialog

Both mutation actions are role-aware:

- `Assign` disabled for unauthorized accounts.
- `Unassign` disabled for unauthorized accounts.

Both handlers independently reject unauthorized calls.

## Defense in depth

The existing WRITE-mode guard remains in place. A class assignment now requires:

```text
Authorized role (Admin / Manager)
        +
WRITE mode
        +
Teacher lifecycle/business rules
```

This prevents accidental access through direct signal invocation while keeping
the normal UI disabled for unauthorized accounts.
