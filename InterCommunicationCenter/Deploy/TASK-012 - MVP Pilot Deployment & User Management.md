# TASK-012 - MVP Pilot Deployment & User Management

Version: 1.0

Priority: 🔴 CRITICAL

Estimated Time: 5~7 Days

Owner: DeepSeek

Status: READY

---

# Background

CenterManager MVP is functionally complete.

The following workspaces are ready.

✅ Student Workspace

✅ Class Workspace

✅ Teaching Workspace

✅ Finance Workspace

The next milestone is NOT adding features.

The goal is to prepare the system for
real-world pilot operation.

---

# Objective

Transform the current development system
into a deployable MVP.

Support multiple real users.

Teachers

Receptionists

Finance

Admin

The system must no longer assume
a single administrator account.

---

# Sprint Scope

Included

✅ User Management

✅ Account Management

✅ Role Assignment

✅ Initial Password

✅ Password Reset

✅ Account Activation

✅ Pilot Deployment Preparation

✅ System Configuration

---

Not Included

❌ Employee Attendance

❌ Payroll

❌ Leave Request

❌ Performance Review

---

# PART 1

User Management

Implement

User Management

inside

Admin Workspace.

Only Admin can manage users.

---

Functions

Create User

Edit User

Deactivate User

Reset Password

Assign Roles

Unlock Account

Delete User (optional)

---

# User Information

Fields

Username

Display Name

Email (optional)

Phone (optional)

Role

Status

Created Date

Last Login

Password Reset Required

---

# Roles

Admin

Teacher

Reception

Finance

Support multiple roles
if architecture already supports RBAC.

---

# Account Status

Active

Inactive

Locked

Pending

Only Active users
can log in.

---

# Password

Admin creates

temporary password.

On first login

User must change password.

---

# Password Reset

Admin

↓

Reset Password

↓

Temporary Password

↓

Force Change Password

---

# First Login Workflow

User

↓

Login

↓

Temporary Password

↓

Force Password Change

↓

Continue

Mandatory.

---

# Account Lock

Optional

After

5 failed logins

↓

Temporary Lock

Reuse current Authentication
if possible.

---

# PART 2

Pilot Configuration

Add

System Configuration

Page

Examples

Center Name

Address

Phone

Email

Logo

Currency

Timezone

Academic Year

These values are used
throughout the system.

---

# PART 3

Deployment Readiness

Review

Default Data

Seed Data

Default Admin

Configuration Files

Database Initialization

Environment Variables

Backup Procedure

Restore Procedure

---

# PART 4

Operational Safety

Review

Permission Matrix

Role Matrix

Navigation Visibility

Workspace Visibility

Unauthorized Access

All menus
must respect RBAC.

---

# PART 5

Audit

Record

User Login

Password Reset

Account Creation

Account Disable

Role Change

Reuse Timeline
where appropriate.

---

# UI

Admin Workspace

↓

Users

Display

Username

Display Name

Role

Status

Last Login

Actions

Simple table.

Reuse Design System.

---

# Deliverables

User Management

Role Assignment

Password Reset

Force Password Change

Pilot Configuration

Deployment Checklist

Regression Report

---

# Acceptance Criteria

✔ Admin can create users.

✔ Teacher account works.

✔ Reception account works.

✔ Finance account works.

✔ Password reset works.

✔ First login password change works.

✔ RBAC enforced.

✔ Navigation filtered by role.

✔ Build passes.

---

# Pilot Test Accounts

Create

admin

teacher_demo

reception_demo

finance_demo

with temporary passwords.

Document credentials
for pilot only.

---

# Regression Checklist

Authentication

RBAC

Student Workspace

Class Workspace

Teaching Workspace

Finance Workspace

Timeline

Permissions

Build

---

# Definition of Done

The system is considered

Pilot Ready

when

Multiple users can operate simultaneously.

Each role only sees
its authorized workspaces.

No administrator intervention
is required during normal operation.

The system can be installed
and used by a real training center.