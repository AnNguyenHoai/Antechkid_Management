# Sprint 1 - Collaboration Foundation

**Project:** CenterManager Collaboration Platform  
**Sprint:** 1 / 3  
**Priority:** Critical  
**Status:** READY

---

# Sprint Goal

Transform CenterManager from a **Single User Desktop Application** into a **Single Writer / Multiple Reader Platform**.

This sprint introduces the Collaboration Runtime and the concept of **Read Mode** and **Write Mode**.

**Git synchronization is NOT part of this sprint.**

Deliverable:

```
READ MODE

↓

Request WRITE

↓

WRITE MODE

↓

Save

↓

READ MODE
```

---

# Architecture Constraints

This sprint must follow the Platform Specifications.

No shortcuts.

Do not hardcode collaboration logic inside UI.

Create reusable Platform Services.

Business modules must remain unchanged.

---

# Work Package 1
## Collaboration Runtime

Create a new platform package.

Suggested structure

```
platform/
    collaboration/
        collaboration_manager.py
        edit_session_manager.py
        lock_manager.py
        mode_manager.py
        collaboration_context.py
```

Responsibilities

### CollaborationManager

High-level façade.

Coordinates collaboration services.

Must expose

- current_mode()
- request_write()
- release_write()

---

### ModeManager

Owns

READ

WRITE

Only one current mode.

---

### EditSessionManager

Owns

Current Edit Session

Session ID

Session Owner

Session Start Time

Session State

No Git logic.

---

### LockManager

Owns

Acquire

Release

Validation

Current Lock

Lock timeout (future)

---

# Acceptance Criteria

Platform Runtime starts successfully.

Managers are registered.

No UI dependency.

---

# Work Package 2
## Metadata System

Create

```
runtime/

    metadata/

        lock.json

        version.json

        deployment.json
```

If missing

create automatically.

---

## lock.json

Initial

```json
{
    "locked": false,
    "owner": null,
    "session_id": null,
    "started_at": null
}
```

---

## version.json

Initial

```json
{
    "platform_version": 1
}
```

---

## deployment.json

Initial

```json
{
    "profile": "Standalone"
}
```

---

# Acceptance Criteria

Metadata folder automatically created.

Metadata automatically initialized.

No database dependency.

---

# Work Package 3
## Read Mode

Application Startup

↓

READ MODE

Default state

READ

Restrictions

Disable

Save

Delete

Import

Edit

Everything else remains available.

Browsing remains fully functional.

---

# Acceptance Criteria

Application starts in READ mode.

All edit actions disabled.

---

# Work Package 4
## Write Request

Workflow

```
User

↓

Request Write

↓

Check Lock

↓

Acquire Lock

↓

WRITE MODE
```

No Git.

Only local lock.

Failure

↓

Remain READ.

---

# Acceptance Criteria

Only one active Write Session.

---

# Work Package 5
## Save Workflow

Workflow

```
WRITE

↓

Save

↓

Release Lock

↓

READ
```

Save automatically returns to READ.

---

# Acceptance Criteria

Cannot remain permanently in WRITE.

---

# Work Package 6
## Status Bar

Add Collaboration Status Widget.

Display

```
Mode

READ / WRITE

Current User

Current Version

Deployment Profile
```

Future fields

Git Status

Connection

Heartbeat

Reserve space now.

---

# Acceptance Criteria

Status updates live.

No polling required.

---

# Work Package 7
## Notification

Create notifications

Write Acquired

Write Released

Write Failed

Mode Changed

Notification Service only.

Do not use QMessageBox directly.

---

# Work Package 8
## Platform Events

Publish

WriteRequested

WriteGranted

WriteReleased

ModeChanged

These must use the Event Bus.

---

# Work Package 9
## Tests

Required

Unit Tests

ModeManager

LockManager

EditSessionManager

Integration Tests

Application Startup

Read Mode

Write Mode

Release Mode

Manual Tests

Startup

Request Write

Save

Return Read

Restart

---

# Non-Goals

Do NOT implement

Git

Pull

Push

Commit

Credentials

Repository

Synchronization

Heartbeat

Recovery

Backup

Version Increment

These belong to Sprint 2 and Sprint 3.

---

# Deliverables

- Collaboration Runtime
- Mode Manager
- Lock Manager
- Edit Session Manager
- Metadata initialization
- READ / WRITE workflow
- Collaboration Status Bar
- Event integration
- Notification integration
- Full test coverage

---

# Definition of Done

- Application starts successfully.
- Default mode is READ.
- User can request WRITE.
- Lock prevents multiple WRITE sessions.
- Save automatically returns to READ.
- Metadata files are generated automatically.
- No regression in existing features.
- pytest passes.
- No architecture violations.
- No dead code.
- No debug prints.