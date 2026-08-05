# 780_DEVELOPER_GUIDE.md

Version: 1.0

Status: DRAFT

Document Type: Engineering Guide

Owner: OpenAI & AnTechKids

Depends On

740_IMPLEMENTATION_GUIDE.md

750_CODING_STANDARD.md

760_PROJECT_STRUCTURE.md

770_REFERENCE_IMPLEMENTATION.md

---

# Table of Contents

1. Purpose
2. Development Philosophy
3. Development Workflow
4. Daily Development Cycle
5. Feature Development
6. Bug Fix Workflow
7. Refactoring Rules
8. Pull Request Process
9. Code Review
10. Testing Strategy
11. Documentation Rules
12. Release Readiness
13. Developer Checklist
14. Summary

---

# 1. Purpose

This guide defines

how developers work

inside the CenterManager project.

Architecture explains

the Platform.

This guide explains

the engineering process.

---

# 2. Development Philosophy

Every change

must improve

at least one of

Correctness

Readability

Maintainability

Testability

Reliability

Never sacrifice

architecture

for short-term convenience.

---

# 3. Development Workflow

Every task follows

exactly the same lifecycle.

```

Issue

↓

Analysis

↓

Architecture Review

↓

Implementation

↓

Unit Test

↓

Integration Test

↓

Code Review

↓

Merge

↓

Release

```

No shortcut

is allowed.

---

# 4. Daily Development Cycle

Start Day

↓

Pull Latest Code

↓

Run Test Suite

↓

Update Local Branch

↓

Implement Assigned Task

↓

Run Tests Again

↓

Commit

↓

Push

↓

Create Pull Request

Every working day

starts

with synchronization.

---

# 5. Feature Development

Every feature

must begin with

Architecture Analysis.

Questions

Which Module?

Which Workspace?

Which Contract?

Which Events?

Which Services?

Only after

architecture is clear

should coding begin.

---

# 6. Bug Fix Workflow

Bug Report

↓

Reproduce

↓

Root Cause Analysis

↓

Fix

↓

Regression Test

↓

Review

↓

Merge

Never fix

without reproducing

the issue first.

---

# 7. Refactoring Rules

Refactoring

must not change

observable behavior.

Allowed

Improve naming

Split classes

Extract methods

Reduce duplication

Improve performance

Forbidden

Hidden behavior changes

Breaking contracts

Skipping tests

---

# 8. Pull Request Process

Every Pull Request

must include

Purpose

Architecture Impact

Files Changed

Testing Performed

Screenshots (if UI)

Known Limitations

Reviewer Notes

Small Pull Requests

are preferred.

---

# 9. Code Review

Every review evaluates

Architecture Compliance

Coding Standard

Dependency Direction

Error Handling

Logging

Tests

Documentation

Performance

Security

Correctness

---

# 10. Testing Strategy

Minimum requirement

Unit Tests

Required

Integration Tests

Required

Smoke Test

Required

Manual Verification

Required

End-to-End Tests

Recommended

No feature

is complete

without testing.

---

# 11. Documentation Rules

Documentation

must evolve

with implementation.

Every feature

updates

Architecture (if needed)

API

Developer Notes

Release Notes

Examples

Outdated documentation

is considered

technical debt.

---

# 12. Branch Strategy

Recommended

main

Stable production.

develop

Integration branch.

feature/<name>

New features.

bugfix/<name>

Bug fixes.

release/<version>

Release stabilization.

hotfix/<name>

Production fixes.

Branch names

must be descriptive.

---

# 13. Commit Rules

Commit messages

follow

```
[type] Short summary

Examples

[Feature]

Student attendance export

[Fix]

Correct PDF layout

[Refactor]

Split StudentService

[Test]

Add attendance integration tests

[Docs]

Update architecture specification
```

Every commit

should represent

one logical change.

---

# 14. Release Readiness

Before release

verify

All Tests Pass

No Debug Code

No TODO

No Console Print

Documentation Updated

Migration Tested

Performance Verified

Release Notes Written

Every release

must be reproducible.

---

# 15. Developer Checklist

Before closing a task

Developer confirms

Architecture followed

Tests passed

Code reviewed

Logs added

Documentation updated

No dead code introduced

No warnings ignored

Feature verified manually

---

# 16. Anti-patterns

Do not

Commit broken builds

Bypass review

Skip tests

Ignore architecture

Mix responsibilities

Create circular dependencies

Leave debug code

Duplicate business logic

Large unreviewable PRs

---

# 17. Engineering Principles

The project values

Predictability

Consistency

Quality

Maintainability

Communication

Ownership

Long-term thinking

Engineering quality

is more important

than development speed.

---

# 18. Future Evolution

Future versions

may include

Automated Architecture Validation

Static Analysis Gates

Quality Metrics

Performance Gates

AI Code Review

Continuous Documentation

These additions

extend

the engineering workflow

without changing

its principles.

---

# Summary

The Developer Guide defines

how software is built,

reviewed,

tested,

and maintained

inside the CenterManager project.

It ensures

every contributor

follows

the same engineering process,

making the Platform

consistent,

predictable,

and maintainable

throughout its lifetime.