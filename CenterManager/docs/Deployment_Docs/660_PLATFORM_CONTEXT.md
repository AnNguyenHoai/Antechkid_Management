# 660_PLATFORM_CONTEXT.md

Version: 1.0

Status: DRAFT

Document Type: Platform Context Specification

Owner: OpenAI & AnTechKids

Depends On

550_PLATFORM_RUNTIME.md

560_MODULE_MODEL.md

650_CONFIGURATION_SERVICE.md

---

# Table of Contents

1. Purpose
2. Why Platform Context Exists
3. Context Philosophy
4. Platform Context Model
5. Context Hierarchy
6. Context Ownership
7. Context Lifecycle
8. Context Propagation
9. Context Immutability
10. Context Access
11. Context Relationships
12. Future Evolution

---

# 1. Purpose

Platform Context provides the unified execution context of CenterManager.

Every subsystem executes inside exactly one Platform Context.

Platform Context represents

the current runtime state

of the entire application.

---

# 2. Why Platform Context Exists

Without Platform Context

every subsystem creates

its own context model.

Examples

RuntimeContext

WorkspaceContext

ModuleContext

SessionContext

UserContext

These contexts gradually diverge.

Platform Context unifies them.

---

# 3. Context Philosophy

Context answers one question.

> "What is the current execution environment?"

Context never owns

Business Logic

Persistence

Synchronization

Configuration

Context only describes state.

It never changes business behavior.

---

# 4. Platform Context Model

PlatformContext

contains

RuntimeContext

DeploymentContext

ConfigurationContext

UserContext

WorkspaceContext

ModuleContext

SessionContext

NotificationContext

HealthContext

VersionContext

All Platform state

is reachable

through Platform Context.

---

# 5. Context Hierarchy

PlatformContext

↓

RuntimeContext

↓

ModuleContext

↓

WorkspaceContext

↓

SessionContext

Each child

inherits

its parent context.

Children may add information.

They never remove parent information.

---

# 6. Runtime Context

Runtime Context contains

Application State

Deployment Profile

Platform Services

Startup Time

Current Version

Runtime Health

Only one Runtime Context exists.

---

# 7. User Context

User Context contains

Current User

Roles

Permissions

Authentication State

Locale

Preferences

User Context never stores

business objects.

---

# 8. Module Context

Module Context contains

Module Name

Module State

Configuration

Capabilities

Registered Workspaces

Business Services

Every Module owns one Module Context.

---

# 9. Workspace Context

Workspace Context contains

Selected Object

Current View

Edit Mode

Filter State

Navigation State

Workspace Status

Workspace Context exists only

while the Workspace is active.

---

# 10. Session Context

Session Context contains

Session ID

Owner

Started Time

Heartbeat

Edit State

Platform Version

Synchronization Status

Session Context exists

only during Edit Sessions.

---

# 11. Configuration Context

Configuration Context contains

Deployment Profile

Feature Flags

Runtime Configuration

Platform Settings

Configuration Context

is immutable

after Runtime initialization.

---

# 12. Version Context

Version Context contains

Platform Version

Database Revision

Deployment Revision

Synchronization Revision

Version State

Version Context

is updated

after successful publication.

---

# 13. Health Context

Health Context contains

Storage Health

Synchronization Health

Deployment Health

Runtime Health

Health Context

is read-only.

---

# 14. Context Lifecycle

Application Start

↓

Platform Context Created

↓

Runtime Initialized

↓

Modules Registered

↓

Workspace Activated

↓

Edit Session Started

↓

Edit Session Closed

↓

Workspace Released

↓

Runtime Shutdown

↓

Platform Context Destroyed

---

# 15. Context Propagation

Platform Context

flows downward.

Platform Context

↓

Module Context

↓

Workspace Context

↓

Session Context

Context never flows upward.

Children

must never modify parent context.

---

# 16. Context Immutability

Platform Context

is immutable.

Subcontexts

may update

their local state only.

Global context

remains protected.

---

# 17. Context Access

Subsystems obtain context

through

Context Provider.

Subsystems never

construct contexts manually.

This guarantees

consistency.

---

# 18. Architectural Rules

Rule CTX1

Exactly one Platform Context.

Rule CTX2

Context flows downward.

Rule CTX3

Children never modify parents.

Rule CTX4

Context describes state.

Never behavior.

Rule CTX5

Platform Context owns

all execution state.

---

# 19. Future Evolution

Future contexts may include

Cloud Context

Device Context

Analytics Context

AI Context

Tenant Context

Remote Session Context

The hierarchy remains unchanged.

---

# Summary

Platform Context is the execution state model of CenterManager.

It unifies every subsystem under one context hierarchy.

By separating execution state from business logic,

the Platform gains

consistency,

predictability,

and extensibility.

Every subsystem speaks

the same contextual language,

making future evolution significantly simpler.
