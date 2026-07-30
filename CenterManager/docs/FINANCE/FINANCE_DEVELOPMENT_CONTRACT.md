# FINANCE_DEVELOPMENT_CONTRACT.md

Version: 1.0

Status: Mandatory

---

# Purpose

This document defines mandatory development rules for implementing
Finance Module.

Every developer must follow these rules.

Violating these rules is considered an architecture violation.

---

# 1. Architecture First

Never change architecture without approval.

If implementation conflicts with architecture

STOP

Report

Wait for decision.

Do NOT redesign.

---

# 2. Single Responsibility Principle

Each module owns exactly one responsibility.

Student

↓

Business

Finance

↓

Money

Dashboard

↓

Visualization

Timeline

↓

History

Never mix responsibilities.

---

# 3. Finance Owns Transactions

Finance stores only

Income

Expense

Never store

Outstanding

Revenue

Profit

Statistics

Dashboard values

These values are calculated.

---

# 4. Student Owns Tuition

Student owns

Registered Course

Course Fee

Discount

Enrollment

Finance must never duplicate them.

---

# 5. Outstanding Rule

Wrong

Store Outstanding in database.

Correct

Outstanding

=

Expected Tuition

-

Paid Amount

Realtime calculation only.

---

# 6. Dashboard Rule

Dashboard is Read Only.

Dashboard

must never

Insert

Update

Delete

Dashboard only reads services.

---

# 7. API Rule

Every API

Controller

↓

Permission

↓

Validation

↓

Service

↓

Repository

↓

Database

Controller must never access database directly.

---

# 8. Service Rule

Business logic belongs to Service Layer.

Never implement business logic inside

Controller

React Component

Repository

---

# 9. Repository Rule

Repository

ONLY

Database access.

No calculation.

No validation.

No business logic.

---

# 10. Validation Rule

Validate

before

calling Service.

Examples

Amount

Student

Payment Method

Category

Status

---

# 11. Permission Rule

Never trust Frontend.

Every Finance API

must validate

Permission.

Unauthorized

↓

403

---

# 12. UI Rule

Current UI has been approved.

Do NOT redesign.

Allowed

Bug Fix

CRUD

Small UX improvements

Not Allowed

New Layout

New Navigation

Large Component Refactor

---

# 13. Timeline Rule

Every financial transaction

must generate

Timeline Event.

Income

↓

Student Timeline

Expense

↓

System Timeline

---

# 14. Data Duplication Rule

Every data has only one owner.

Never duplicate

Student Name

Course Fee

Outstanding

Revenue

Statistics

Always reference original source.

---

# 15. Error Handling Rule

400

Validation

401

Authentication

403

Permission

404

Not Found

409

Conflict

500

Unexpected Error

Never return ambiguous error.

---

# 16. Logging Rule

Every financial transaction

must be logged.

Log

User

Action

Time

Target

Success

Failure

---

# 17. Transaction Rule

Income creation

must be atomic.

Either

Everything succeeds

OR

Everything rolls back.

Never leave partial updates.

---

# 18. Testing Rule

Every task must include

Unit Test

API Test

Manual Test

No feature is complete without testing.

---

# 19. Performance Rule

Dashboard

<1 second

Income Search

<500 ms

Expense Search

<500 ms

Pagination mandatory.

---

# 20. Code Review Checklist

Developer must verify

Architecture

Business Logic

Permission

Validation

Performance

Security

Testing

before creating Pull Request.

---

# 21. Forbidden

Developer MUST NOT

Store calculated data.

Duplicate business data.

Bypass Service Layer.

Skip permission validation.

Redesign UI.

Modify unrelated modules.

Assume missing business rules.

If uncertain

STOP

Report

Wait for clarification.

---

# 22. Development Philosophy

Correct Architecture

>

Correct Business Logic

>

Clean Code

>

UI Polish

A feature is only complete when

Architecture

Business

Security

Testing

are all correct.