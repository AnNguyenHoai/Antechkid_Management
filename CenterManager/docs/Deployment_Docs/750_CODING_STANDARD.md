# 750_CODING_STANDARD.md

Version: 1.0

Status: DRAFT

Document Type: Engineering Standard

Owner: OpenAI & AnTechKids

Depends On

740_IMPLEMENTATION_GUIDE.md

---

# Table of Contents

1. Purpose
2. Philosophy
3. General Principles
4. Naming Conventions
5. File Organization
6. Class Design
7. Method Design
8. Error Handling
9. Logging
10. Dependency Rules
11. Documentation
12. Testing
13. Review Checklist
14. Future Evolution

---

# 1. Purpose

This document defines the coding standards
used throughout the CenterManager project.

Its goal is

Consistency

Readability

Maintainability

Predictability

The Coding Standard applies to

all source code,

regardless of module or contributor.

---

# 2. Philosophy

Code is read

far more often

than it is written.

Optimize code

for readability,

not cleverness.

Every developer

should write code

that another developer

can understand immediately.

---

# 3. General Principles

Prefer simplicity.

Avoid unnecessary abstraction.

One responsibility

per class.

One purpose

per function.

Duplicate code

only after careful consideration.

Premature optimization

is discouraged.

---

# 4. Naming Conventions

Classes

PascalCase

Examples

StudentService

AttendanceRepository

GitSynchronizationProvider

Methods

snake_case

Examples

create_student()

publish_version()

acquire_edit_session()

Variables

snake_case

Examples

student_name

session_id

platform_version

Constants

UPPER_CASE

Examples

DEFAULT_TIMEOUT

MAX_RETRY_COUNT

---

# 5. File Organization

One primary class

per file.

File name

matches primary class.

Example

student_service.py

↓

StudentService

Avoid

multiple unrelated classes

inside one file.

---

# 6. Class Design

Each class

has exactly one responsibility.

Good

StudentService

AttendanceService

ReportExporter

Bad

StudentManager

PlatformHelper

UtilityClass

Generic names

are discouraged.

---

# 7. Method Design

Methods should

perform one logical task.

Recommended length

< 50 lines

Large methods

should be decomposed.

Method names

should describe behavior.

Avoid

process()

handle()

execute()

Prefer

publish_version()

export_student_report()

record_attendance()

---

# 8. Constructor Rules

Constructors

receive dependencies.

Constructors

do not perform work.

Forbidden

Database migration

Synchronization

Long calculations

Network requests

during construction.

---

# 9. Error Handling

Raise

specific exceptions.

Avoid

catching Exception

unless at application boundaries.

Every exception

must either

be handled

or propagated.

Silent failures

are forbidden.

---

# 10. Logging

Logging

must use

Logging Service.

Forbidden

print()

debug leftovers

temporary console output

Every warning

and every error

must be logged.

---

# 11. Dependency Rules

Presentation

depends on

Application.

Application

depends on

Domain.

Domain

depends on

Contracts.

Infrastructure

implements Contracts.

Forbidden

Domain

↓

UI

Repository

↓

Workspace

Module

↓

Module

Cross-module communication

must use Events or Contracts.

---

# 12. Documentation

Every public class

must include

Purpose

Responsibilities

Dependencies

Every public method

should include

Parameters

Return Value

Exceptions

Complex algorithms

must include

implementation notes.

---

# 13. Type Hints

All public methods

must use

Python type hints.

Example

```python
def create_student(
    request: CreateStudentRequest
) -> Student:
```

Avoid

untyped interfaces.

---

# 14. Testing

Every new feature

must include tests.

Preferred order

Unit Test

↓

Integration Test

↓

End-to-End Test

Bug fixes

must include

regression tests.

---

# 15. Review Checklist

Every Pull Request

must answer

Does this follow architecture?

Does this follow naming rules?

Are dependencies correct?

Are exceptions handled?

Are logs sufficient?

Are tests included?

Is documentation updated?

---

# 16. Forbidden Practices

Do not

Hardcode paths

Use global mutable state

Create circular dependencies

Mix UI and business logic

Access SQLite directly from UI

Call Git directly from business code

Duplicate business rules

Suppress exceptions silently

---

# 17. Recommended Practices

Prefer

Dependency Injection

Immutable objects

Small classes

Clear naming

Composition over inheritance

Explicit interfaces

Meaningful logs

High test coverage

---

# 18. Refactoring Guidelines

Refactoring

must preserve

behavior.

Refactoring

may improve

structure,

clarity,

performance,

maintainability.

Architecture Contracts

must remain stable.

---

# 19. Code Style

Maximum line length

100–120 characters.

Use blank lines

to separate logical sections.

Avoid deeply nested code.

Prefer

early return

over

nested if statements.

---

# 20. Future Evolution

Future standards may define

Async Guidelines

Performance Rules

Memory Optimization

Thread Safety

Python Version Migration

These extensions

must remain compatible

with the existing Coding Standard.

---

# Summary

The Coding Standard ensures that every contributor
writes code in a consistent,
predictable,
and maintainable style.

Architecture defines the structure.

Implementation Guide defines the process.

Coding Standard defines the craftsmanship.

Together they provide a stable engineering foundation
for the long-term evolution of CenterManager.