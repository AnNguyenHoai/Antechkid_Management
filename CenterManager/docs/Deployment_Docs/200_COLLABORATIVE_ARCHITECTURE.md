# 200_COLLABORATIVE_ARCHITECTURE.md

Version: 1.0

Status: DRAFT

Document Type: Platform Architecture

Owner: OpenAI & AnTechKids

Depends On

000_PLATFORM_VISION.md

100_ARCHITECTURE_PRINCIPLES.md

---

# Table of Contents

1. Purpose
2. Platform Overview
3. Platform Responsibilities
4. High-Level Architecture
5. Core Components
6. Collaboration Engine
7. Edit Session
8. Synchronization Pipeline
9. Version Control
10. Storage Layer
11. Deployment Strategy
12. Component Relationships
13. Platform Events
14. Future Evolution

---

# 1. Purpose

This document defines the complete architecture of the CenterManager Collaboration Platform (CCP).

It explains:

- major components
- responsibilities
- communication boundaries
- ownership
- lifecycle

This document intentionally avoids implementation details.

Implementation belongs to lower-level specifications.

---

# 2. Platform Overview

CenterManager is divided into two independent worlds.

Business World

Infrastructure World

Business World contains educational knowledge.

Infrastructure World provides technical capabilities.

The Collaboration Platform is the bridge between them.

```

Presentation

↓

Application

↓

Business

↓

Persistence

=========================

Collaboration Platform

=========================

Storage

Deployment

```

The Business Layer must never communicate directly with infrastructure.

---

# 3. Platform Responsibilities

The Collaboration Platform owns every responsibility related to collaborative operation.

It is responsible for:

Edit Sessions

Synchronization

Version Tracking

Deployment Strategy

Workspace State

Publishing

Recovery

Notifications

Business logic remains completely outside the platform.

---

# 4. High-Level Architecture

```

                    CenterManager

                           │

                   Presentation Layer

                           │

                  Application Services

                           │

                   Business Services

                           │

                  Persistence Layer

                           │

══════════════════════════════════════

          Collaboration Platform

══════════════════════════════════════

        │

        ├── Edit Session Manager

        ├── Collaboration Provider

        ├── Workspace Manager

        ├── Synchronization Manager

        ├── Version Manager

        ├── Notification Manager

        └── Storage Adapter

                           │

══════════════════════════════════════

               Deployment Backend

══════════════════════════════════════

SQLite

Git

Server

Future Storage

```

---

# 5. Core Components

The Collaboration Platform contains seven core components.

Each component owns exactly one responsibility.

## Edit Session Manager

Owns

Edit Session lifecycle.

Responsible for

Request Edit

Create Session

Close Session

Cancel Session

Session Recovery

It does NOT synchronize data.

---

## Workspace Manager

Owns

Workspace state.

States include

VIEW

EDIT

SYNCING

LOCKED

Workspace Manager never modifies business data.

---

## Synchronization Manager

Responsible for

Synchronizing

Publishing

Receiving Updates

Conflict Detection

Synchronization Manager knows nothing about Students or Finance.

---

## Version Manager

Responsible for

Platform Version

Version History

Current Version

Version Comparison

Change Detection

Version Manager owns platform metadata.

---

## Notification Manager

Responsible for

Platform Notifications.

Examples

New Version

Sync Failed

Edit Session Expired

Connection Lost

Notification Manager never modifies data.

---

## Collaboration Provider

The single entry point into the Collaboration Platform.

Business Layer communicates only with this interface.

No other platform component is visible outside.

---

## Storage Adapter

Responsible for deployment-specific operations.

Examples

Git

Gitea

GitHub

Server

Future providers

Storage Adapter isolates infrastructure from the platform.

---

# 6. Collaboration Engine

The Collaboration Engine is composed of

Edit Session Manager

Workspace Manager

Synchronization Manager

Version Manager

Notification Manager

These components together implement collaborative behavior.

The Collaboration Engine never depends on deployment technology.

---

# 7. Edit Session

Edit Session is the Aggregate Root of the platform.

Everything related to editing belongs to this concept.

Lifecycle

```

VIEW

↓

Request Edit

↓

Session Created

↓

Editing

↓

Commit

↓

Publish

↓

Close Session

↓

VIEW

```

Properties

Session ID

Owner

Started

Heartbeat

Workspace

Current Version

Status

Deployment Profile

Edit Session represents a business activity,

not a technical lock.

---

# 8. Synchronization Pipeline

Every synchronization follows the same pipeline.

```

Business Commit

↓

Persistence Commit

↓

Synchronization Request

↓

Storage Adapter

↓

Deployment Backend

↓

Publish Success

↓

Increase Version

↓

Notify Clients

```

Business Layer never calls Storage Adapter directly.

---

# 9. Version Control

Versioning belongs to the platform.

Every successful publish creates

exactly one new platform version.

Version consists of

Version Number

Timestamp

Publisher

Deployment Profile

Commit Reference

Future platforms may extend metadata.

---

# 10. Storage Layer

Storage is completely abstract.

```

Storage Adapter

↓

Git Adapter

↓

GitHub

```

or

```

Storage Adapter

↓

Server Adapter

↓

REST API

```

Business Layer cannot distinguish between deployments.

---

# 11. Deployment Strategy

Deployment is selected at runtime.

Supported profiles

Standalone

Collaborative

Server

The selected profile determines which Storage Adapter is instantiated.

Nothing above the Collaboration Platform changes.

---

# 12. Component Relationships

```

Business

↓

Collaboration Provider

↓

Edit Session Manager

↓

Synchronization Manager

↓

Storage Adapter

↓

Deployment Backend

```

Workspace Manager

Version Manager

Notification Manager

operate independently,

communicating through platform events.

No component owns another component's responsibility.

---

# 13. Platform Events

The platform communicates internally through events.

Examples

EditSessionCreated

EditSessionClosed

SynchronizationStarted

SynchronizationCompleted

VersionChanged

WorkspaceChanged

StorageConnected

StorageDisconnected

Events reduce direct dependencies between components.

---

# 14. Future Evolution

The architecture intentionally supports future extensions.

Examples

Cloud Deployment

Multiple Storage Providers

Automatic Backup

Background Synchronization

Conflict Analysis

Server Deployment

Distributed Authentication

None of these extensions should require redesigning Business Services.

The Collaboration Platform exists specifically to isolate future infrastructure evolution.

---

# Architecture Summary

Business owns knowledge.

Persistence owns data.

Collaboration owns synchronization.

Storage owns deployment.

Each layer has one responsibility.

No layer violates ownership.

This separation enables CenterManager to evolve

from

Standalone Desktop

to

Collaborative Platform

without redesigning its business architecture.
