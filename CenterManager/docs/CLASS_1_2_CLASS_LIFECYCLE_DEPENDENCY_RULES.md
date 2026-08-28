# CLASS-1.2 — CLASS LIFECYCLE & DEPENDENCY RULES

## Lifecycle contract

A class has two workspace lifecycle states:

```text
ACTIVE <-> ARCHIVED
```

Archive is a **soft archive** using `Class.deleted_at`.

## Archive policy

Archiving a class does **not** delete or cascade-delete historical data.

The following are preserved:

- Teacher assignment history
- Enrollment history
- Sessions
- Attendance and other session-owned history
- Class timeline

While a class is archived, it is frozen against operational mutation.

Blocked until restore:

- Class edit
- New teacher assignment
- Teacher unassignment
- New student enrollment
- Student withdrawal from the archived class
- Session create
- Session update
- Session delete

Read-only access to historical data remains available through repository/service
paths that explicitly support historical inspection.

## Restore policy

Restoring a class only clears `deleted_at`.

Restore does not recreate or reactivate dependencies. Existing historical
relationships remain exactly as they were before archive.

## Why this policy

Archive means:

> preserve the academic record while preventing accidental changes.

This avoids destructive cascades and makes restore deterministic.
