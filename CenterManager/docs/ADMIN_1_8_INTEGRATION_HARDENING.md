# ADMIN 1.8 — Integration & Hardening

## Scope
- Complete Backup & Recovery integration in Admin Workspace.
- Enforce backup.view, backup.create, backup.restore boundaries.
- Require WRITE mode for create/restore.
- Create mandatory pre-restore safety backup.
- Audit BACKUP_CREATED and BACKUP_RESTORED actions.
- Add regression coverage across Admin 1.0–1.7 contracts present in the codebase.

## Verification
- `python -m compileall -q src`
- Admin regression suite: 24 passed.
