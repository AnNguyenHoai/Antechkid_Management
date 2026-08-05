# 600_STORAGE_ADAPTER.md

Version: 1.0

Status: DRAFT

Document Type: Platform Storage Specification

Owner: OpenAI & AnTechKids

Depends On

000_PLATFORM_VISION.md

100_ARCHITECTURE_PRINCIPLES.md

200_COLLABORATIVE_ARCHITECTURE.md

400_EDIT_SESSION_PROTOCOL.md

500_COLLABORATION_PROVIDER.md

575_PLATFORM_CONTRACT.md

580_EVENT_BUS.md

---

# Table of Contents

1. Purpose
2. Why Storage Adapter Exists
3. Design Philosophy
4. Responsibilities
5. Storage Contract
6. Storage Lifecycle
7. Storage States
8. Storage Operations
9. Transaction Rules
10. Version Rules
11. Error Model
12. Health Monitoring
13. Extension Rules
14. Future Storage Providers

---

# 1. Purpose

Storage Adapter isolates the Platform from every physical storage technology.

Business Modules never know

SQLite

Git

Server

Cloud

Filesystem

The Platform communicates only through the Storage Contract.

---

# 2. Why Storage Adapter Exists

Without Storage Adapter

Business Layer

↓

SQLite

Later

SQLite

↓

Git

Later

Git

↓

Server

Business would continuously change.

Storage Adapter prevents this.

---

# 3. Design Philosophy

Storage is an implementation detail.

Business owns information.

Storage owns persistence.

Synchronization owns publication.

Deployment owns topology.

Responsibilities never overlap.

---

# 4. Responsibilities

Storage Adapter owns

Read

Write

Publish

Acquire Lock

Release Lock

Version Metadata

Storage Health

Connection State

Storage Adapter never owns

Business Rules

Synchronization Logic

Permissions

Workspace

---

# 5. Storage Contract

Every implementation must satisfy the following interface.

```python
class StorageAdapter:

    initialize()

    shutdown()

    load()

    save()

    publish()

    rollback()

    acquire()

    release()

    current_version()

    health()

    capabilities()
```

The interface is stable.

Implementations may differ.

---

# 6. Storage Lifecycle

CREATED

↓

INITIALIZING

↓

READY

↓

ACTIVE

↓

PUBLISHING

↓

READY

↓

SHUTDOWN

Every provider follows the same lifecycle.

---

# 7. Storage States

NOT_INITIALIZED

INITIALIZING

READY

READ_ONLY

WRITE_RESERVED

PUBLISHING

ERROR

SHUTDOWN

Only one state is active.

---

# 8. Storage Operations

Initialize

Load

Save

Publish

Rollback

Reserve

Release

Query Version

Health Check

Capabilities

No additional operation should bypass this contract.

---

# 9. Transaction Rules

Storage never performs Business Transactions.

Business Transaction

↓

Persistence Commit

↓

Storage Save

↓

Storage Publish

Storage is the last stage.

---

# 10. Version Rules

Storage stores

Platform Version

Storage Version

Provider Version

Storage never decides version semantics.

Version Manager owns semantics.

Storage only persists them.

---

# 11. Lock Rules

Storage owns

physical reservation.

It does NOT own

Edit Session.

Example

Edit Session

↓

Acquire Storage Reservation

↓

Publish

↓

Release Reservation

Storage Reservation is an implementation detail.

---

# 12. Error Model

Storage Errors

StorageUnavailable

PublishFailed

ReservationDenied

VersionMismatch

StorageCorrupted

HealthCheckFailed

Business never receives provider-specific errors.

---

# 13. Health Monitoring

Every provider exposes

Health Status

Latency

Storage Size

Connection

Current Version

Provider Name

Deployment Profile

Health information is read-only.

---

# 14. Capability Discovery

Every provider advertises its capabilities.

Example

Read

Write

Publish

Rollback

Versioning

Background Sync

Locking

Future providers may expose additional capabilities.

---

# 15. Extension Rules

Future providers

must implement

the Storage Contract.

Examples

GitStorageAdapter

SQLiteStorageAdapter

ServerStorageAdapter

CloudStorageAdapter

S3StorageAdapter

OneDriveStorageAdapter

GoogleDriveStorageAdapter

No Platform redesign is required.

---

# 16. Storage Independence

Business

↓

Repository

↓

Persistence

↓

Storage Adapter

Business never knows

which provider

is active.

---

# 17. Architectural Rules

Rule SA1

Storage owns persistence.

Rule SA2

Storage never owns business.

Rule SA3

Storage never owns synchronization.

Rule SA4

Storage implementations are replaceable.

Rule SA5

Provider-specific behavior never leaks outside.

Rule SA6

Platform communicates only through Storage Contract.

---

# 18. Future Evolution

Future Storage Providers

Git

Git LFS

Server

REST

GraphQL

Cloud

Database Cluster

Offline Cache

All coexist through one contract.

---

# Summary

Storage Adapter is the persistence abstraction of CenterManager.

It separates business knowledge from storage technology.

It provides a stable contract for every deployment strategy.

By standardizing persistence,

the Platform can evolve

without changing Business Modules.