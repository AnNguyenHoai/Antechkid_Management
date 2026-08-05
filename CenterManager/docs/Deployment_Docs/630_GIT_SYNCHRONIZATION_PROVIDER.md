# 630_GIT_SYNCHRONIZATION_PROVIDER.md

Version: 1.0

Status: DRAFT

Document Type: Git Synchronization Provider Specification

Owner: OpenAI & AnTechKids

Implements

620_SYNCHRONIZATION_PROVIDER.md

---

# Table of Contents

1. Purpose
2. Scope
3. Design Goals
4. Repository Structure
5. Synchronization Model
6. Edit Session Workflow
7. Git Workflow
8. Lock Model
9. Version Model
10. Metadata
11. Failure Recovery
12. Offline Mode
13. Security
14. Limitations
15. Future Migration

---

# 1. Purpose

GitSynchronizationProvider implements the Synchronization Contract using Git.

It allows multiple CenterManager clients to collaborate without requiring a database server.

Git is used only as a synchronization backend.

Git is NOT the database.

SQLite remains the source of truth.

---

# 2. Scope

Responsibilities

✔ Synchronize SQLite database

✔ Synchronize platform metadata

✔ Synchronize Edit Session state

✔ Synchronize reports

✔ Synchronize backups (optional)

Not responsible for

Business Rules

Persistence

Deployment Policy

Authentication

UI

---

# 3. Design Goals

The implementation prioritizes

Simple deployment

Deterministic synchronization

Easy recovery

Human-readable metadata

Minimal user interaction

Offline-first operation

---

# 4. Repository Structure

Repository Root

```
CenterManagerData/

│

├── database/
│      center.db
│
├── metadata/
│      version.json
│      lock.json
│      deployment.json
│
├── reports/
│
├── backup/
│
└── logs/
```

Database

contains persistent business data.

Metadata

contains platform state.

Reports

contains exported documents.

Backup

contains snapshots.

Logs

contains synchronization diagnostics.

---

# 5. Synchronization Model

The provider synchronizes

Committed SQLite Database

↓

Platform Metadata

↓

Generated Reports

Synchronization order

must never change.

---

# 6. Edit Session Workflow

Normal workflow

```
READ MODE

↓

Request Edit

↓

git fetch

↓

git pull

↓

Validate Version

↓

Acquire Lock

↓

Commit lock.json

↓

Push

↓

EDIT MODE

↓

Save Database

↓

Commit SQLite

↓

Commit Metadata

↓

Push

↓

Release Lock

↓

Commit lock.json

↓

Push

↓

READ MODE
```

Only one Edit Session exists.

---

# 7. Git Workflow

Every synchronization follows

```
Fetch

↓

Pull

↓

Verify Clean Repository

↓

Commit

↓

Push

↓

Verify Push

↓

Complete
```

Git merge is intentionally avoided.

Only fast-forward synchronization is supported.

---

# 8. Lock Model

The lock is represented by

metadata/lock.json

Example

```json
{
    "locked": true,
    "owner": "teacher01",
    "machine": "PC-01",
    "session_id": "SESSION-001",
    "started_at": "...",
    "heartbeat": "...",
    "platform_version": 42
}
```

The lock file is authoritative.

Only one active lock exists.

---

# 9. Version Model

Platform Version

is stored in

metadata/version.json

Example

```json
{
    "platform_version": 42,
    "database_revision": 120,
    "last_commit": "abcdef123",
    "updated_at": "...",
    "updated_by": "teacher01"
}
```

Version Manager owns semantics.

Git only transports the metadata.

---

# 10. Commit Policy

Every commit follows the same format.

```
[module]

short summary

User:
Session:
Version:
```

Examples

```
[Student]

Update student profile

User: admin
Session: ES-0001
Version: 42
```

```
[Finance]

Receive tuition payment

User: reception01
Session: ES-0002
Version: 43
```

Commit history becomes an audit trail.

---

# 11. Pull Policy

Pull occurs

Application Startup

Request Edit

Manual Refresh

Recovery

Automatic polling is not required.

---

# 12. Push Policy

Push occurs only

after successful Commit.

Push never occurs

during editing.

Push never occurs

before Persistence Commit.

---

# 13. Conflict Policy

The implementation avoids merge conflicts.

Rules

One Edit Session

↓

One Commit

↓

One Publish

↓

One Version

If another version exists

during Request Edit

↓

Pull Latest

↓

Restart Request

Conflict prevention

is preferred over conflict resolution.

---

# 14. Failure Recovery

Possible failures

Push Failed

↓

Retry

Pull Failed

↓

Retry

Application Crash

↓

Lock Recovery

Network Lost

↓

Offline Queue

Repository Corrupted

↓

Restore Backup

Each failure has one deterministic recovery path.

---

# 15. Offline Mode

The application may continue

in READ mode

while offline.

Entering EDIT mode

requires synchronization.

No offline editing

is supported

in Version 1.

---

# 16. Security

Private Repository

HTTPS

Personal Access Token

Encrypted Local Credential Store

Git credentials are never stored

inside the database.

---

# 17. Performance Targets

Repository Size

< 500 MB

Normal Synchronization

< 5 seconds

Edit Session Acquisition

< 2 seconds

Startup Synchronization

< 3 seconds

These values are design targets.

---

# 18. Known Limitations

Only one writer.

No concurrent editing.

Whole database synchronization.

SQLite binary file.

No partial synchronization.

These limitations are accepted by design.

---

# 19. Future Evolution

Future implementations may support

Incremental database synchronization

Delta synchronization

Git LFS

Background synchronization

Automatic conflict analysis

Remote approval workflow

Server migration

The Synchronization Contract remains unchanged.

Only the implementation evolves.

---

# Architecture Summary

Business Layer

↓

Persistence Provider (SQLite)

↓

GitSynchronizationProvider

↓

Git Repository

↓

GitHub / Gitea / GitLab

SQLite remains the single source of truth.

Git acts as a transport mechanism.

The platform never treats Git as a database.

This implementation satisfies the Synchronization Contract while preserving deployment independence.