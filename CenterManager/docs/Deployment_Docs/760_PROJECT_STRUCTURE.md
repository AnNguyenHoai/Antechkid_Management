# 760_PROJECT_STRUCTURE.md

Version: 1.0

Status: DRAFT

Document Type: Engineering Standard

Owner: OpenAI & AnTechKids

Depends On

740_IMPLEMENTATION_GUIDE.md

750_CODING_STANDARD.md

---

# Table of Contents

1. Purpose
2. Philosophy
3. Top-Level Structure
4. Source Tree
5. Module Structure
6. Shared Components
7. Platform Components
8. Infrastructure Components
9. Runtime Structure
10. Tests
11. Documentation
12. Naming Rules
13. Dependency Rules
14. Future Evolution

---

# 1. Purpose

This document standardizes

the directory structure

of the CenterManager project.

The directory structure is part of the architecture.

Developers must not reorganize

the project arbitrarily.

---

# 2. Philosophy

A project should be

predictable.

Every developer should know

where a file belongs

without asking.

Folder names describe

responsibilities,

not implementation details.

---

# 3. Top-Level Structure

```
CenterManager/

│

├── docs/

├── migrations/

├── runtime/

├── scripts/

├── src/

├── tests/

├── tools/

├── requirements.txt

├── pyproject.toml

└── run.py
```

Every top-level directory

has one responsibility.

---

# 4. Source Tree

```
src/

    centermanager/

        application/

        domain/

        infrastructure/

        platform/

        presentation/

        shared/

        bootstrap/

        app.py
```

Responsibilities

application

Business orchestration.

domain

Business model.

platform

Platform Runtime.

infrastructure

External implementations.

presentation

UI.

shared

Reusable components.

bootstrap

Application startup.

---

# 5. Module Structure

Each business module follows

exactly the same layout.

Example

```
student/

    application/

    domain/

    repositories/

    services/

    events/

    presentation/

    module.py
```

Examples

student/

finance/

teaching/

classroom/

employee/

No module

may invent

its own structure.

---

# 6. Platform Structure

```
platform/

    runtime/

    configuration/

    context/

    event_bus/

    notification/

    logging/

    backup/

    health/

    security/

    version/

    collaboration/

    providers/
```

Platform contains

cross-cutting services only.

No business logic

belongs here.

---

# 7. Infrastructure Structure

```
infrastructure/

    persistence/

        sqlite/

        postgres/

    synchronization/

        git/

        server/

    deployment/

    filesystem/

    reporting/

    adapters/
```

Infrastructure implements

Platform Contracts.

Infrastructure never owns

Business Rules.

---

# 8. Presentation Structure

```
presentation/

    workspaces/

    dialogs/

    widgets/

    navigation/

    themes/

    resources/
```

Presentation owns

only

user interaction.

Business logic

must never appear here.

---

# 9. Shared Structure

```
shared/

    dto/

    enums/

    exceptions/

    contracts/

    utilities/

    value_objects/
```

Shared components

must remain

framework-independent.

---

# 10. Bootstrap Structure

```
bootstrap/

    startup.py

    dependency_container.py

    module_loader.py

    workspace_loader.py

    shutdown.py
```

Bootstrap assembles

the Platform.

Nothing else.

---

# 11. Runtime Structure

```
runtime/

    database/

    backup/

    reports/

    logs/

    cache/

    temp/
```

Runtime contains

generated data only.

Source code

must never be placed

inside runtime.

---

# 12. Tests Structure

```
tests/

    unit/

    integration/

    contracts/

    e2e/

    performance/

    fixtures/
```

Every production layer

has corresponding tests.

---

# 13. Documentation Structure

```
docs/

    architecture/

    engineering/

    implementation/

    api/

    decisions/

    release_notes/
```

Architecture documents

never mix

with implementation notes.

---

# 14. Naming Rules

Directory names

use

snake_case.

Modules

use

singular nouns.

Examples

student

teacher

attendance

report

Avoid

helpers/

misc/

temp/

new/

old/

test2/

legacy/

Generic folder names

are forbidden.

---

# 15. Dependency Rules

Allowed

Presentation

↓

Application

↓

Domain

↓

Contracts

↓

Platform

↓

Infrastructure

Forbidden

Platform

↓

Presentation

Domain

↓

Infrastructure

Module

↓

Module

Cross-module communication

must use

Events

or

Contracts.

---

# 16. File Placement Rules

Every file

has exactly one home.

Examples

Student Entity

↓

domain/

SQLite Repository

↓

infrastructure/persistence/sqlite/

Attendance Dialog

↓

presentation/dialogs/

Version Manager

↓

platform/version/

Never duplicate

the same responsibility

across folders.

---

# 17. Migration Rules

When introducing

new architecture,

existing code

must migrate

gradually.

Temporary compatibility layers

are allowed.

Permanent duplicates

are forbidden.

---

# 18. Architectural Rules

Rule PS1

Directory structure

reflects architecture.

Rule PS2

One responsibility

per directory.

Rule PS3

Modules share

the same structure.

Rule PS4

Platform is business-independent.

Rule PS5

Infrastructure implements

contracts only.

Rule PS6

Presentation owns UI only.

Rule PS7

Runtime contains

generated artifacts only.

---

# 19. Future Evolution

Future directories may include

analytics/

ai/

telemetry/

plugins/

sdk/

cloud/

No existing directory

should change responsibility.

New capabilities

extend

the structure,

never reorganize it.

---

# Summary

The Project Structure defines the physical organization
of the CenterManager source code.

A stable directory structure

improves

discoverability,

maintainability,

onboarding,

code reviews,

and long-term evolution.

Architecture defines the logical system.

Project Structure defines its physical form.

Both must evolve together.