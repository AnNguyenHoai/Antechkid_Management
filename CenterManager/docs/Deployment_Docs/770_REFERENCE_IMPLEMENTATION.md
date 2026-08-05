# 770_REFERENCE_IMPLEMENTATION.md

Version: 1.0

Status: DRAFT

Document Type: Reference Implementation

Owner: OpenAI & AnTechKids

Depends On

All Architecture Documents

740_IMPLEMENTATION_GUIDE.md

750_CODING_STANDARD.md

760_PROJECT_STRUCTURE.md

---

# Table of Contents

1. Purpose
2. Why Reference Implementation Exists
3. Philosophy
4. Reference Module
5. Directory Structure
6. Startup Flow
7. Request Flow
8. Event Flow
9. Repository Flow
10. Workspace Flow
11. Testing Flow
12. Extension Guide
13. Anti-patterns
14. Checklist
15. Summary

---

# 1. Purpose

This document provides

the canonical implementation

of a CenterManager Module.

It demonstrates

how Platform Specifications

translate into production code.

All future modules

should follow this reference.

---

# 2. Why Reference Implementation Exists

Architecture describes

concepts.

Implementation Guide describes

principles.

Reference Implementation shows

actual implementation.

Developers learn

by reading working examples.

---

# 3. Philosophy

One module

should demonstrate

every Platform Contract.

If developers

can implement

one correct module,

they can implement

every module.

---

# 4. Reference Module

The Student Module

is designated

as the official

Reference Module.

Reason

It touches

CRUD

Search

Report

PDF

Attendance

Finance

Permission

Workspace

Export

Events

Notifications

Almost every Platform capability.

---

# 5. Directory Structure

```
student/

    application/

        commands/

        queries/

        services/

    domain/

        entities/

        value_objects/

        events/

    repositories/

        contracts/

    infrastructure/

        sqlite/

    presentation/

        workspaces/

        dialogs/

        widgets/

    tests/

    module.py
```

Every future module

uses the same structure.

---

# 6. Startup Flow

Bootstrap

↓

Module Loader

↓

Student Module

↓

Register Services

↓

Register Events

↓

Register Workspace

↓

Register Navigation

↓

READY

Module startup

must never

access UI directly.

---

# 7. Request Flow

User Click

↓

Workspace

↓

Application Service

↓

Repository Contract

↓

Persistence Provider

↓

Result

↓

Workspace Update

Business logic

always executes

inside Application Services.

---

# 8. Event Flow

Student Created

↓

Publish Event

↓

Event Bus

↓

Notification

↓

Logging

↓

Statistics

↓

Report

Publishers

never know

subscribers.

---

# 9. Repository Flow

Application Service

↓

Repository Contract

↓

SQLite Repository

↓

Persistence Provider

↓

SQLite

Business Layer

never knows

SQLite.

---

# 10. Workspace Flow

Workspace

owns

Navigation

Selection

Filtering

Rendering

Workspace

never owns

Business Logic.

---

# 11. Error Flow

SQLite Error

↓

Persistence Exception

↓

Application Exception

↓

Presentation Error

↓

Dialog

Only Presentation

formats messages

for users.

---

# 12. Logging Flow

Application Service

↓

Logging Service

↓

Log Entry

↓

Log File

Logging

never blocks

business execution.

---

# 13. Notification Flow

Business Event

↓

Notification Service

↓

Workspace

↓

User

Notification creation

belongs to

Notification Service.

---

# 14. Testing Flow

Entity

↓

Unit Test

Service

↓

Service Test

Repository

↓

Integration Test

Workspace

↓

UI Test

Module

↓

Smoke Test

Each layer

is tested independently.

---

# 15. Extension Guide

To create

a new module

Developer should

Copy

Reference Module

Rename

Domain Objects

Replace

Business Rules

Keep

Architecture

The structure

must remain identical.

---

# 16. Anti-patterns

Never

Access SQLite

from Workspace.

Never

Call another Module directly.

Never

Read Configuration Files.

Never

Publish mutable Events.

Never

Instantiate Providers

inside Business code.

Never

Use print()

for diagnostics.

---

# 17. Review Checklist

Module follows

Project Structure

Coding Standard

Platform Contracts

Dependency Rules

Testing Rules

Logging Rules

Notification Rules

Security Rules

Architecture Rules

Every review

begins

with this checklist.

---

# 18. Reference Metrics

Recommended targets

Module Startup

<100 ms

Workspace Open

<200 ms

CRUD Operation

<50 ms

Search

<100 ms

PDF Export

<2 s

Unit Test Coverage

>90%

These are engineering goals.

---

# 19. Future Evolution

Future reference modules

may include

Finance Module

Teaching Module

Employee Module

Reporting Module

The Student Module

remains

the canonical example.

---

# Summary

Reference Implementation bridges

architecture

and

production code.

It transforms

Platform Specifications

into

working engineering practices.

Every new module

should resemble

the Reference Module

in structure,

responsibility,

and coding style.

Consistency is the objective.

Architecture is the foundation.

Reference Implementation is the blueprint.