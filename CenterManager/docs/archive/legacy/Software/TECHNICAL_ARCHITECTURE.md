# TECHNICAL_ARCHITECTURE.md

Version: 1.0

Status: APPROVED

Architecture Level: Technical

Depends On

- ARCHITECTURE_V2.md
- DOMAIN_MODEL.md
- APPLICATION_ARCHITECTURE.md

---

# 1. Purpose

This document defines the technical architecture of CenterManager.

It specifies:

- Technology Stack
- Runtime Architecture
- Code Organization
- Infrastructure
- Deployment Strategy
- Engineering Standards

This document is technology-oriented.

Business decisions belong to previous documents.

---

# 2. Architecture Philosophy

Technical decisions must support the Business Architecture.

Technology is replaceable.

Business logic is not.

Every technical component should exist to support the Domain Model.

---

# 3. Technology Stack

## Frontend

Recommended

Flutter

Reason

- Cross Platform

- Desktop

- Web

- Mobile

Single codebase.

---

## Backend

Recommended

ASP.NET Core

Reason

- Excellent performance

- Strong dependency injection

- Mature ecosystem

- Enterprise ready

---

## Database

Recommended

PostgreSQL

Reason

- Open Source

- ACID

- Excellent relational modeling

- Strong indexing

---

## Cache

Redis

Purpose

- Session

- Temporary data

- Performance

---

## Object Storage

S3 Compatible Storage

Examples

- MinIO

- AWS S3

Purpose

Store

- Lesson Material

- Student Portfolio

- Attachments

---

# 4. Overall Technical Architecture

```
                Client

                    │

         Flutter Application

                    │

          HTTPS / REST API

                    │

          ASP.NET Backend

                    │

     Application Layer

                    │

        Domain Layer

                    │

 Repository Implementation

                    │

 PostgreSQL / Redis / Storage
```

---

# 5. Frontend Architecture

```
Presentation

↓

Application

↓

Domain

↓

Infrastructure
```

Presentation

Flutter Widgets

Application

Riverpod Controllers

Use Cases

Domain

Business Objects

Infrastructure

REST API

Storage

---

# 6. Backend Architecture

```
Controller

↓

Application Service

↓

Domain Service

↓

Repository

↓

Database
```

Controllers contain no business logic.

Business logic belongs to Domain.

---

# 7. API Architecture

Style

RESTful API

Resource-oriented.

Examples

```
/students

/classes

/sessions

/invoices
```

Rules

Plural nouns

Versioned APIs

```
/api/v1/
```

Stateless requests.

---

# 8. Authentication

Authentication

JWT

Authorization

Role Based Access Control (RBAC)

Roles

Teacher

Reception

Finance

HR

Manager

Administrator

Permissions are evaluated at the Application Layer.

---

# 9. Database Principles

Use relational design.

Every Aggregate Root maps to a primary table.

Examples

Student

Course

Class

Session

Invoice

Employee

Child entities use foreign keys.

Avoid duplicated information.

---

# 10. State Management

Frontend

Riverpod

Reasons

- Compile-time safety

- Testability

- Modular architecture

State categories

UI State

Application State

Cached State

Remote State

Business objects remain immutable where possible.

---

# 11. Dependency Injection

Backend

Built-in ASP.NET DI

Frontend

Riverpod Providers

Every dependency is injected.

Avoid global singletons except for infrastructure services.

---

# 12. Logging

Levels

Debug

Information

Warning

Error

Critical

Business events should also be logged.

Examples

Student Created

Attendance Submitted

Invoice Paid

---

# 13. Error Handling

Categories

Validation

Business Rule

Network

Authentication

Infrastructure

Unexpected

Errors should be standardized.

Example

```
{
    code,
    message,
    details
}
```

---

# 14. Configuration

Environment-based.

Examples

Development

Testing

Staging

Production

Configuration never hardcoded.

---

# 15. File Storage

Documents

Homework

Lesson Materials

Images

Student Portfolio

Attachments

Stored outside database.

Database stores metadata only.

---

# 16. Background Jobs

Suitable for

Report Generation

Notification

Backup

Email

Data Synchronization

Long-running jobs should not block requests.

---

# 17. Security

HTTPS Only

Password Hashing

JWT Expiration

Refresh Token

Permission Validation

Audit Log

Sensitive data encrypted at rest where required.

---

# 18. Performance

Pagination

Lazy Loading

Caching

Index Optimization

Background Processing

Avoid N+1 database queries.

---

# 19. Monitoring

Health Check Endpoint

Application Metrics

Error Monitoring

Performance Metrics

Database Monitoring

Audit Logs

System should be observable.

---

# 20. Deployment

Docker Containers

Backend

Frontend

Database

Redis

Reverse Proxy

Deployment should be automated.

---

# 21. CI/CD

Pipeline

```
Commit

↓

Build

↓

Unit Test

↓

Static Analysis

↓

Package

↓

Deploy

↓

Smoke Test
```

Deployment should be repeatable.

---

# 22. Coding Standards

Naming

Consistent

Formatting

Automatic

Lint

Mandatory

Code Review

Mandatory

Architecture Review

Required for structural changes.

---

# 23. Package Structure

```
src/

    app/

    core/

    shared/

    modules/

        student/

        teacher/

        finance/

        hr/

        report/

        admin/
```

Every Workspace follows the same package structure.

---

# 24. Testing Strategy

Unit Tests

Application Tests

Integration Tests

API Tests

UI Tests

End-to-End Tests

Business rules should be covered by automated tests.

---

# 25. Technical Principles

Principle 1

Technology supports Business—not the opposite.

---

Principle 2

Business logic must remain framework-independent.

---

Principle 3

Every layer has a single responsibility.

---

Principle 4

Infrastructure can be replaced without changing the Domain.

---

Principle 5

Automation is preferred over manual processes.

---

Principle 6

Observability and maintainability are first-class concerns.

---

# 26. Future Evolution

Potential future enhancements

- GraphQL Gateway
- Event Bus
- Microservices
- AI Services
- Offline Synchronization
- Multi-tenant Architecture
- Plugin System

These should build on the existing architecture rather than replace it.

---

# Technical Architecture Status

Version

1.0

Status

APPROVED

Frozen

YES