# TEACHER-1.4 — Document Storage Hardening

## Implemented

### Upload
The document file is copied before DB persistence, but DB failure now triggers compensating cleanup:

```text
copy file
→ persist DB
→ commit
```

On persistence failure:

```text
rollback by session context
→ remove copied file
→ remove empty teacher folder
→ re-raise error
```

Storage names now use UUIDs to avoid same-second filename collisions.

### Delete
The DB record is now deleted and committed before physical file cleanup:

```text
delete DB row
→ commit
→ best-effort physical delete
```

This prevents the previous failure mode where a DB transaction failure could leave a DB row pointing to an already deleted file.

If physical cleanup fails after commit, DB consistency remains intact and the remaining file is an orphan. Empty teacher folders are cleaned up automatically when possible.

## Non-goal
A global runtime orphan-file sweeper is not added here because TEACHER-1.4 is limited to teacher document transaction consistency. Runtime artifact cleanup should be handled centrally rather than each service deleting unrelated files.
