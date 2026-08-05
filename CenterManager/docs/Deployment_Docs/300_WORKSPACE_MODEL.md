# 300_WORKSPACE_MODEL.md

Version: 1.0

Status: DRAFT

Document Type: Platform Domain Specification

Owner: OpenAI & AnTechKids

Depends On

000_PLATFORM_VISION.md

100_ARCHITECTURE_PRINCIPLES.md

200_COLLABORATIVE_ARCHITECTURE.md

---

# Table of Contents

1. Purpose
2. Why Workspace Exists
3. Definition
4. Workspace Responsibilities
5. Workspace Ownership
6. Workspace Lifecycle
7. Workspace State Machine
8. Workspace Communication
9. Workspace Isolation
10. Workspace Registration
11. Future Workspace Types
12. Architectural Rules
13. Examples

---

# 1. Purpose

This document defines the Workspace Model of CenterManager.

Workspace is one of the fundamental concepts of the Collaboration Platform.

Every business capability exposed to users exists through a Workspace.

Workspace is not merely a UI page.

Workspace is a bounded operational context.

---

# 2. Why Workspace Exists

Traditional desktop software often organizes functionality around windows or dialogs.

CenterManager intentionally avoids this model.

Instead,

the application is divided into independent Workspaces.

Examples

Student Workspace

Finance Workspace

Teaching Workspace

Class Workspace

Teacher Workspace

Reporting Workspace

Administration Workspace

Each Workspace represents

one operational responsibility.

---

# 3. Definition

A Workspace is

> A bounded operational environment responsible for one business capability.

A Workspace owns

User Interaction

Business Flow

Workspace State

Navigation

Session Participation

A Workspace does NOT own

Database

Synchronization

Deployment

Storage

Versioning

These belong to the Collaboration Platform.

---

# 4. Workspace Responsibilities

Every Workspace is responsible for

Displaying business information

Receiving user interaction

Requesting Edit Session

Executing business commands

Displaying synchronization status

Refreshing data

Nothing more.

---

# 5. Workspace Ownership

Each Workspace owns exactly one business capability.

Example

Student Workspace

↓

Student Management

Finance Workspace

↓

Financial Management

Teaching Workspace

↓

Teaching Activities

Reporting Workspace

↓

Reports

Administration Workspace

↓

System Administration

Workspace boundaries must remain clear.

Business responsibilities may never overlap.

---

# 6. Workspace Lifecycle

Every Workspace follows the same lifecycle.

Application Start

↓

Workspace Registration

↓

Initialization

↓

Load Data

↓

Ready

↓

Active

↓

Inactive

↓

Disposed

No Workspace should invent its own lifecycle.

---

# 7. Workspace State Machine

Each Workspace exists in one of the following states.

UNINITIALIZED

↓

INITIALIZING

↓

READY

↓

ACTIVE

↓

EDIT_REQUESTED

↓

EDITING

↓

SYNCHRONIZING

↓

READY

↓

DISPOSED

Descriptions

UNINITIALIZED

Workspace object does not exist.

INITIALIZING

Dependencies are created.

READY

Workspace is available.

ACTIVE

User is interacting.

EDIT_REQUESTED

Waiting for Collaboration Platform.

EDITING

Edit Session active.

SYNCHRONIZING

Publishing changes.

DISPOSED

Workspace released.

---

# 8. Workspace Communication

Workspace must never communicate directly with another Workspace.

Forbidden

Student Workspace

↓

Finance Workspace

Instead

Student Workspace

↓

Application Service

↓

Business Service

↓

Repository

↓

Collaboration Platform

↓

Application Service

↓

Finance Workspace

Communication occurs only through services or platform events.

---

# 9. Workspace Isolation

Every Workspace is isolated.

Workspace may not

Modify another Workspace's UI

Access another Workspace's state

Control another Workspace's lifecycle

Import another Workspace directly

Isolation guarantees maintainability.

---

# 10. Workspace Registration

All Workspaces register through Workspace Manager.

Example

WorkspaceManager

↓

register(StudentWorkspace)

↓

register(FinanceWorkspace)

↓

register(ClassWorkspace)

↓

register(TeachingWorkspace)

Workspace Manager becomes the single source of truth.

No Workspace creates another Workspace.

---

# 11. Workspace Participation

When Collaboration Mode is enabled,

each Workspace participates in the Collaboration Platform.

Responsibilities include

Observe platform version

Observe Edit Session

Observe synchronization status

React to platform notifications

Workspace never controls collaboration.

It only reacts.

---

# 12. Workspace Refresh Policy

Workspace refresh must follow consistent rules.

Automatic Refresh

When

Platform Version changes.

Manual Refresh

When

User requests.

Forbidden

Continuous polling inside Workspace.

Version monitoring belongs to Collaboration Platform.

---

# 13. Workspace Activation Policy

Only one Workspace is active.

Multiple Workspaces may exist.

Only one receives user interaction.

State transitions

READY

↓

ACTIVE

↓

READY

Activation never creates or destroys Workspace.

Activation only changes focus.

---

# 14. Workspace Context

Every Workspace owns a Workspace Context.

Workspace Context contains

Current User

Deployment Profile

Platform Version

Edit Session

Permissions

Selected Object

Workspace State

Workspace Context is immutable from outside.

---

# 15. Workspace Events

Workspace communicates through events.

Examples

WorkspaceActivated

WorkspaceDeactivated

WorkspaceLoaded

WorkspaceRefreshed

EditRequested

EditStarted

EditFinished

SynchronizationCompleted

Events reduce coupling.

---

# 16. Future Workspace Types

The model supports future Workspaces.

Examples

Employee Workspace

Payroll Workspace

Inventory Workspace

CRM Workspace

Parent Portal Workspace

Online Classroom Workspace

No architectural changes are required.

---

# 17. Architectural Rules

Rule W1

One Workspace

↓

One Business Capability

Rule W2

Workspace never owns infrastructure.

Rule W3

Workspace never communicates directly with another Workspace.

Rule W4

Workspace lifecycle is standardized.

Rule W5

Workspace state is managed by Workspace Manager.

Rule W6

Workspace participates in collaboration,

but never controls it.

Rule W7

Workspace owns presentation,

not persistence.

---

# 18. Example

Student Workspace

↓

Display Student List

↓

User clicks Edit

↓

Request Edit Session

↓

Collaboration Platform

↓

Approved

↓

Student Workspace enters EDITING

↓

User modifies student

↓

Business Service

↓

Repository

↓

Persistence

↓

Synchronization

↓

Platform publishes

↓

Workspace returns READY

Student Workspace never knows

whether deployment uses

SQLite

Git

Server

or future storage.

---

# Summary

Workspace is the operational boundary of CenterManager.

It represents business responsibility,

not application windows.

All Workspaces follow

one lifecycle,

one communication model,

one collaboration model,

and one architectural contract.

This standardization enables the platform to grow

without increasing architectural complexity.
