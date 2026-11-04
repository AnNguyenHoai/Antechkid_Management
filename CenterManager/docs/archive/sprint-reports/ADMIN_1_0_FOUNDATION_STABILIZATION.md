# ADMIN-1.0 — Foundation & Safety Stabilization

## Objective

Stabilize the Admin Workspace before expanding user or role-management
functionality.

## Safety contract

Admin UI pages may be created while collaboration is still unavailable.
A UI state check must never crash the application by calling
`CollaborationManager.ensure_write()` directly.

All Admin pages use the safe `can_write()` helper:

- collaboration missing -> read-only
- collaboration not initialized -> read-only
- collaboration exception -> read-only
- initialized WRITE owner -> write enabled

## Notification contract

Admin pages can safely operate even when no notification service is injected.
Notifications are best-effort and never become a crash path.

## Permission boundary

Admin pages are explicitly mapped to permissions:

- Users -> `user.manage`
- Settings -> `setting.update`
- Git Config -> `setting.update`
- Diagnostics -> `user.manage`

The shell rejects navigation to a page when the current user lacks its
permission.

## Write-state contract

`MainWindow` remains the owner of transaction WRITE mode and propagates state
through `set_write_enabled()`.

Admin pages disable write actions in READ mode. User context actions are also
disabled in READ mode.

## Git configuration safety

Save is enabled only when all conditions are true:

1. collaboration WRITE mode is active
2. encrypted bundle text exists
3. the field is currently editable
4. the current bundle passed validation
5. Git config service is available

Testing a bundle never writes configuration. Invalid or changed bundles reset
validation state.

## Scope boundary

ADMIN-1.0 does not redesign User CRUD, role management, password policy, or
Git credential format. Those remain follow-up tasks.
