# PR F — Authoritative Password Change & Authentication Persistence

## Problem

A forced password change was committed only to the local runtime database during
login. On the next startup, authoritative Git synchronization materialized the
shared database again and restored the previous password hash.

## Fix

- Production login verifies credentials but defers a required password mutation
  until collaboration and WriteTransactionManager are initialized.
- The application shell stays restricted while the password flow acquires WRITE.
- Immediate and queued grants reuse the existing authoritative handoff barrier.
- The account is re-read after WRITE acquisition.
- ChangePasswordDialog re-verifies the current password against the fresh
  runtime database and commits the bcrypt hash locally.
- The existing WriteTransactionManager Finish Editing path publishes the change.
- Workspace access is enabled only after publication succeeds and the
  force_password_change flag is re-read as false.
- Cancellation or publication failure is fail-closed.

## Explicit non-changes

This PR does not modify mandatory fresh MAIN synchronization, SHA/generation
fencing, WAL-safe database materialization, RuntimeSyncService publication
internals, or background pull-only behavior. No password-specific Git push path
is introduced.
