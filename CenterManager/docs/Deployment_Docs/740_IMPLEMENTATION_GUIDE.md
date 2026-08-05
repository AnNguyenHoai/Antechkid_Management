# 740_IMPLEMENTATION_GUIDE.md

Version: 1.0

Status: DRAFT

Document Type: Platform Implementation Guide

Owner: OpenAI & AnTechKids

Depends On

All Platform Specifications

---

# Table of Contents

1. Purpose
2. Implementation Philosophy
3. Development Layers
4. Dependency Rules
5. Runtime Assembly
6. Module Development
7. Workspace Development
8. Service Development
9. Repository Development
10. Provider Development
11. Event Development
12. Testing Strategy
13. Coding Rules
14. Review Checklist
15. Future Evolution

---

# 1. Purpose

This document translates

Platform Specifications

into

Implementation Guidelines.

Architecture defines

what the Platform is.

This document defines

how developers implement it.

---

# 2. Implementation Philosophy

Implementation must follow

Architecture.

Architecture must never follow

implementation shortcuts.

When implementation becomes difficult,

improve the implementation,

not the architecture.

Architecture is the source of truth.

---

# 3. Layer Responsibilities

Presentation

↓

Application

↓

Domain

↓

Persistence

↓

Platform

↓

Infrastructure

Dependencies always point downward.

Reverse dependencies are forbidden.

---

# 4. Dependency Rules

Allowed

Presentation

↓

Application

↓

Domain

↓

Repository

↓

Persistence Provider

Forbidden

Repository

↓

Workspace

Workspace

↓

Repository Implementation

Module

↓

Another Module Implementation

Every dependency

must follow

the Platform Architecture.

---

# 5. Runtime Assembly

Application Entry

↓

Bootstrap

↓

Configuration

↓

Deployment Profile

↓

Platform Runtime

↓

Core Services

↓

Modules

↓

Workspaces

↓

Login

↓

READY

No component

may initialize itself.

---

# 6. Module Implementation

Every Module follows

the same structure.

```

StudentModule/

    application/

    domain/

    repositories/

    services/

    events/

    workspace/

    module.py

```

The structure is identical

for every Module.

---

# 7. Workspace Implementation

Workspace owns

UI

Navigation

Interaction

State

Workspace never owns

Business Rules

Persistence

Synchronization

Business operations

must call

Application Services.

---

# 8. Service Implementation

Services contain

business orchestration.

Services

must not

perform UI operations.

Services

must not

read configuration files directly.

Services communicate

through Platform Contracts.

---

# 9. Repository Implementation

Repositories translate

Domain Objects

↓

Persistence Operations.

Repositories

must never contain

Business Rules.

Repositories

depend only on

Persistence Provider.

---

# 10. Provider Implementation

Providers implement

Platform Contracts.

Examples

SQLitePersistenceProvider

GitSynchronizationProvider

StandaloneDeploymentProfile

Every Provider

is replaceable.

Provider-specific behavior

must remain isolated.

---

# 11. Event Implementation

Business Events

must be immutable.

Publishers

never know subscribers.

Subscribers

must remain independent.

Events

must represent

completed facts.

---

# 12. Error Handling

Errors propagate upward.

Infrastructure Errors

↓

Platform Errors

↓

Application Errors

↓

Presentation

Presentation decides

how to display errors.

Business logic

never formats error messages.

---

# 13. Logging

Every Platform Service

logs

Lifecycle

Failures

Warnings

Performance

Business Modules

log only

business-relevant operations.

---

# 14. Testing Strategy

Every layer

has its own tests.

Domain

Unit Tests

Application

Service Tests

Repositories

Integration Tests

Providers

Contract Tests

Runtime

Smoke Tests

End-to-End Tests

No test

should require

the entire Platform

unless explicitly testing integration.

---

# 15. Dependency Injection

Dependencies

must be injected.

Forbidden

```

student = StudentRepository()

```

Allowed

```

StudentService(

repository,

event_bus,

logger

)

```

Object creation belongs

to Bootstrap.

---

# 16. Configuration Usage

Configuration

is accessed only through

Configuration Service.

No module

may parse JSON files.

No module

may hardcode paths.

---

# 17. Code Organization

Business code

must never reference

Git

SQLite

Filesystem

Platform Contracts

hide infrastructure.

---

# 18. Code Review Checklist

Every Pull Request

must answer

Does this violate architecture?

Does this introduce new dependencies?

Does this duplicate existing functionality?

Does this follow Platform Contracts?

Does this improve maintainability?

Architecture compliance

takes priority

over implementation convenience.

---

# 19. Refactoring Rules

Refactoring

must preserve

Platform Contracts.

Internal implementation

may change.

Public Contracts

must remain stable.

Breaking changes

require

architecture review.

---

# 20. Documentation Rules

Every new subsystem

must provide

Architecture

Contract

Implementation Notes

Testing Strategy

Examples

Documentation evolves

with code.

---

# 21. Future Evolution

Future developers

should be able to

implement

Persistence

Synchronization

Deployment

Security

Modules

without changing

Platform Architecture.

The Platform Specification

is intended to remain stable

for many years.

---

# Summary

Implementation exists

to realize

the Platform Architecture.

Developers should think in

Contracts,

Providers,

Modules,

Workspaces,

and Platform Services,

not in files,

frameworks,

or libraries.

When implementation and architecture disagree,

architecture should guide implementation.

Consistency,

replaceability,

and maintainability

are the primary goals of CenterManager.