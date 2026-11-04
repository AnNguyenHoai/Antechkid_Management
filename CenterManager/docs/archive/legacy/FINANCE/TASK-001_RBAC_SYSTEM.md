# TASK-001 - Implement Role & Permission System (RBAC)

Version: 1.0

Priority: 🔴 Critical

Estimated Time: 1~2 Days

Owner: DeepSeek

Status: Ready

---

# Background

CenterManager is entering Phase 2 development.

Before implementing Teacher and Finance modules, the system must support Role-Based Access Control (RBAC).

This task establishes the authorization infrastructure for the entire application.

No business functionality should be implemented in this task.

---

# Objective

Implement a complete RBAC (Role-Based Access Control) system.

The implementation must support:

- User Role
- Permission
- Backend Authorization
- Frontend Route Protection
- Frontend Menu Protection

This infrastructure will be reused by every future module.

---

# Scope

Included

✅ Role Entity

✅ Permission Entity

✅ Role-Permission Mapping

✅ Backend Permission Middleware

✅ Route Guard

✅ Frontend Menu Guard

✅ Seed Default Roles

---

Not Included

❌ Finance Module

❌ Student Module

❌ Teacher Module

❌ Reports

❌ Dashboard

Only infrastructure should be implemented.

---

# System Roles

Create three default roles.

ADMIN

Full Access

--------------------

TEACHER

Teaching Functions Only

--------------------

RECEPTION

Reserved for future use

(No Finance Permission)

---

# Permission List

## Student

student.view

student.create

student.update

student.delete

---

## Teacher

teacher.view

teacher.create

teacher.update

teacher.delete

---

## Finance

finance.view

finance.income.create

finance.income.update

finance.income.delete

finance.expense.create

finance.expense.update

finance.expense.delete

---

## Reports

report.view

---

## Settings

setting.update

---

# Database Design

Create required tables.

roles

permissions

role_permissions

users.role_id

If authentication already exists,

extend existing schema instead of creating duplicated structures.

---

# Backend Requirements

Implement

PermissionService

PermissionGuard

Role Seeder

Permission Seeder

Every protected API must validate permission before entering business logic.

Permission checking must happen before Service Layer.

Never trust frontend.

---

# Frontend Requirements

Implement Menu Guard.

Example

ADMIN

Dashboard

Students

Teachers

Finance

Reports

Settings

----------------------

TEACHER

Dashboard

Students

Classes

Assessment

Finance menu must NOT appear.

----------------------

RECEPTION

Dashboard

Students

Teachers

Finance menu must NOT appear.

---

# Route Protection

Unauthorized route

/finance

↓

403 Page

Unauthorized APIs

↓

403 Forbidden

---

# Deliverables

Database Migration

Role Entity

Permission Entity

Permission Middleware

Seed Data

Frontend Menu Guard

Frontend Route Guard

Documentation

---

# Acceptance Criteria

ADMIN

✔ Can access Finance

✔ Can access Dashboard

✔ Can access Settings

--------------------------------

TEACHER

✔ Finance menu hidden

✔ Finance API returns 403

✔ Finance route blocked

--------------------------------

RECEPTION

✔ Finance menu hidden

✔ Finance API returns 403

✔ Finance route blocked

--------------------------------

Backend

✔ Permission checked before business logic

✔ No permission hardcoded inside controllers

✔ Middleware reusable

---

# Technical Constraints

Do NOT redesign UI.

Do NOT modify unrelated modules.

Do NOT implement Finance.

Do NOT implement Teacher features.

Do NOT change project architecture.

Follow existing coding style.

---

# Development Rules

1.

Every API must go through PermissionGuard.

---

2.

Controllers must never check Role manually.

Always use Permission.

---

3.

Business logic belongs to Service Layer.

---

4.

Repositories only access database.

---

5.

Frontend permission is only for UX.

Backend permission is mandatory.

---

6.

No duplicated permission logic.

Permission checking must be centralized.

---

7.

If existing architecture conflicts with this task,

STOP

Document the issue

Report instead of redesigning.

---

# Testing Checklist

Database Migration

☐ Pass

Role Seeder

☐ Pass

Permission Seeder

☐ Pass

Admin Login

☐ Pass

Teacher Login

☐ Pass

Reception Login

☐ Pass

Menu Hidden

☐ Pass

Route Protection

☐ Pass

API Protection

☐ Pass

Permission Middleware

☐ Pass

---

# Expected Output

A reusable Role-Based Access Control system that becomes the foundation for all future CenterManager modules.

No business module should require changes to this infrastructure.

This task is considered COMPLETE only when all acceptance criteria and tests pass successfully.