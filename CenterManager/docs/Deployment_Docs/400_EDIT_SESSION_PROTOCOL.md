# 400_EDIT_SESSION_PROTOCOL.md

Version: 1.0

Status: DRAFT

Document Type: Platform Protocol Specification

Owner: OpenAI & AnTechKids

Depends On

000_PLATFORM_VISION.md

100_ARCHITECTURE_PRINCIPLES.md

200_COLLABORATIVE_ARCHITECTURE.md

300_WORKSPACE_MODEL.md

---

# Table of Contents

1. Purpose
2. Why Edit Session Exists
3. Edit Session Definition
4. Protocol Overview
5. Lifecycle
6. State Machine
7. Ownership Rules
8. Session Context
9. Session Operations
10. Commit Protocol
11. Synchronization Protocol
12. Failure Recovery
13. Timeout Policy
14. Events
15. Security Rules
16. Extension Points
17. Future Evolution

---

# 1. Purpose

Edit Session is the central protocol of the Collaboration Platform.

It replaces the traditional concept of

Write Permission.

Instead of asking

"Can this user write?"

the platform asks

"Can a new Edit Session be created?"

This distinction is intentional.

Writing is treated as a business activity,

not merely a permission.

---

# 2. Why Edit Session Exists

Traditional desktop software usually grants write access directly.

Problems

- difficult recovery

- no lifecycle

- no ownership

- no audit

- weak synchronization

CCP replaces write permission

with

Edit Session.

Every modification belongs to

exactly one

Edit Session.

---

# 3. Definition

An Edit Session is

a controlled business activity

during which one user owns the right

to modify shared data.

It begins

before editing.

It ends

after publishing.

Everything between these two moments

belongs to the session.

---

# 4. Session Identity

Each Edit Session owns

Session ID

Owner

Machine

Started Time

Last Activity

Workspace

Deployment Profile

Current Version

State

Commit History

The Session ID uniquely identifies

every editing activity.

---

# 5. Session Lifecycle

The protocol always follows

exactly one lifecycle.

```

VIEW

↓

Request Edit

↓

Validate

↓

Create Session

↓

Acquire Ownership

↓

Editing

↓

Commit Requested

↓

Synchronizing

↓

Publish

↓

Close Session

↓

VIEW

```

No alternative lifecycle exists.

---

# 6. Session State Machine

Possible states

IDLE

REQUESTED

VALIDATING

ACTIVE

COMMITTING

SYNCING

COMPLETED

CANCELLED

FAILED

Only one transition is valid at a time.

Illegal transitions must be rejected.

---

# 7. Ownership

At any moment

only one ACTIVE Edit Session

may exist.

Ownership belongs to

the Session

not the User.

If User A closes the session,

ownership disappears.

It is never transferred automatically.

---

# 8. Session Context

Each Edit Session owns immutable metadata.

Session ID

Owner

Machine

Workspace

Created Time

Deployment Profile

Database Version

These values never change.

Mutable values

Current State

Last Activity

Heartbeat

Objects Modified

Commit Count

---

# 9. Session Operations

Supported operations

Create

Validate

Start

Heartbeat

Pause (Reserved)

Resume (Reserved)

Commit

Cancel

Close

Recover

Force Close (Admin)

No additional operations are permitted.

---

# 10. Validation Protocol

Before creating a session

the platform validates

Current Platform State

Workspace Availability

Current Version

Existing Active Session

Deployment Profile

Storage Availability

Validation must succeed

before editing begins.

---

# 11. Heartbeat

Every ACTIVE session periodically reports activity.

Purpose

Detect abandoned sessions.

Prevent stale ownership.

Support recovery.

Heartbeat updates only

Session Activity.

It never modifies business data.

---

# 12. Timeout Policy

Inactive sessions eventually expire.

Timeout is determined

by Deployment Profile.

Example

Standalone

No timeout

Collaborative

30 minutes

Server

Server controlled

Timeout policy belongs to

Collaboration Provider,

not Business Layer.

---

# 13. Commit Protocol

Commit follows

exactly one sequence.

```

Validate

↓

Business Commit

↓

Persistence Commit

↓

Synchronization

↓

Version Increment

↓

Publish

↓

Close Session

```

Commit is atomic.

Either

everything succeeds

or

nothing changes.

Partial publish is forbidden.

---

# 14. Rollback

Rollback may occur

only before Publish.

Once Publish succeeds,

Rollback belongs to

Version Management.

Rollback never partially restores data.

---

# 15. Synchronization

Synchronization begins

only after

Persistence Commit.

Synchronization never starts

during editing.

Synchronization publishes

Platform State,

not business intent.

---

# 16. Version Rule

Exactly one version

is generated

for every successful publish.

One Edit Session

↓

One Publish

↓

One Version

This invariant

must never be violated.

---

# 17. Failure Recovery

Possible failures

Validation Failed

Synchronization Failed

Storage Failure

Application Crash

Power Loss

Network Loss

Unexpected Exception

Recovery is determined

by Session State.

The platform never guesses.

Recovery follows deterministic rules.

---

# 18. Recovery Matrix

ACTIVE

↓

Application Crash

↓

Recovery Candidate

SYNCING

↓

Connection Lost

↓

Retry Publish

REQUESTED

↓

Validation Failed

↓

Cancel Session

FAILED

↓

Manual Recovery

Each failure path

has exactly one recovery strategy.

---

# 19. Events

The protocol emits events.

SessionCreated

SessionValidated

SessionStarted

SessionHeartbeat

CommitStarted

CommitCompleted

PublishStarted

PublishCompleted

SessionClosed

SessionCancelled

SessionRecovered

SessionExpired

Events are immutable.

---

# 20. Security

Business modules

cannot

Create Session

Destroy Session

Force Close Session

Modify Session State

Only Collaboration Provider

owns session lifecycle.

---

# 21. Extension Rules

Future deployments may extend

Storage

Synchronization

Authentication

Recovery

Versioning

without changing

Edit Session semantics.

Edit Session is considered

a stable protocol.

---

# 22. Platform Invariants

These rules must always remain true.

Exactly one ACTIVE session.

Exactly one owner.

Exactly one publish.

Exactly one platform version.

Business commits precede synchronization.

Publish precedes session closure.

Version increments only after publish.

Violation of these rules

constitutes an architectural error.

---

# 23. Sequence Diagram

```

User

↓

Request Edit

↓

Collaboration Provider

↓

Validate

↓

Create Session

↓

Workspace enters EDITING

↓

Business Update

↓

Persistence Commit

↓

Synchronization

↓

Publish

↓

Increase Version

↓

Close Session

↓

Workspace returns VIEW

```

---

# 24. Future Evolution

Future versions may support

Distributed Collaboration

Remote Session

Approval Workflow

Server Deployment

Offline Queue

Cloud Storage

However,

the Edit Session lifecycle

must remain unchanged.

The protocol is considered

the stable contract

between Business Layer

and Collaboration Platform.

---

# Summary

Edit Session is not a lock.

It is not a permission.

It is not a synchronization mechanism.

It is the business protocol

through which

every modification

enters the Collaboration Platform.

All deployment strategies,

storage adapters,

and synchronization mechanisms

must obey this protocol.

This protocol forms the operational kernel

of the CenterManager Collaboration Platform.