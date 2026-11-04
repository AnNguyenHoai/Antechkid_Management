# Finance Module Design

Version: 1.0

Status: Approved

---

# Objective

Finance is the administration module of CenterManager.

Its responsibilities are:

- Record income.
- Record expense.
- Monitor outstanding tuition.
- Generate financial dashboard.

Finance is NOT the starting point of business workflows.

Student remains the business center.

---

# Architecture

Student
        │
        │ Collect Tuition
        ▼
Income Log
        │
        ├───────────────┐
        ▼               ▼
Outstanding      Finance Dashboard
        │
        ▼
Student Timeline

Expense

↓

Expense Log

↓

Finance Dashboard

---

# Workspace

Finance

├── Dashboard
├── Income
├── Expense
└── Outstanding

---

# Income

Purpose

Record every income transaction.

Source

Student Tuition

Book

Robot Fee

Material

Other

---

Entity

Income

id

studentId

classId

courseId

amount

incomeType

paymentMethod

paymentDate

receivedBy

note

createdAt

updatedAt

---

Income Type

Tuition

Robot Fee

Book

Material

Other

---

Payment Method

Cash

Bank Transfer

---

Table

Date

Student

Class

Income Type

Amount

Method

Received By

Note

---

Functions

Search

Filter

Sort

Export

Create

Edit

Delete

---

Workflow

Student

↓

Financial Tab

↓

Collect Tuition

↓

Create Income

↓

Update Outstanding

↓

Update Dashboard

↓

Create Timeline

---

# Expense

Purpose

Record organization expenses.

---

Entity

Expense

id

category

description

amount

paymentMethod

status

paidBy

paymentDate

note

createdAt

updatedAt

---

Category

Teacher Salary

Office Rent

Electricity

Water

Internet

Equipment

Marketing

Office Supply

Other

---

Status

Pending

Completed

---

Functions

Search

Filter

Sort

Export

Create

Edit

Delete

---

Workflow

Finance

↓

Create Expense

↓

Update Dashboard

↓

Create System Timeline

---

# Outstanding

Purpose

Monitor unpaid tuition.

No CRUD.

Automatically calculated.

---

Columns

Student

Class

Expected

Paid

Outstanding

Due Date

---

Formula

Outstanding

=

Expected Tuition

-

Paid Amount

---

# Dashboard

Read Only

---

KPI

Revenue Today

Revenue This Month

Expense Today

Expense This Month

Current Balance

Outstanding Tuition

---

Widgets

Revenue Trend

Expense Trend

Recent Income

Recent Expense

Need Attention

---

Dashboard Data

Dashboard never stores data.

Everything is calculated from

Income

Expense

Outstanding

---

# Student Financial

Location

Student Detail

↓

Financial

---

Display

Expected Tuition

Paid

Outstanding

Payment History

---

Actions

Collect Tuition

View History

Print Receipt

---

# Permission

Teacher

No Finance Access

No Financial Tab

---

Admin

Dashboard

Income

Expense

Outstanding

Export

CRUD

---

Reception (Future)

Collect Tuition Only

No Finance Dashboard

No Expense

---

# Security

Permission is checked on Backend.

UI hiding is NOT security.

Every Finance API must verify permission.

---

# Development Order

Phase 1

Permission

↓

Phase 2

Income

↓

Phase 3

Expense

↓

Phase 4

Outstanding

↓

Phase 5

Dashboard

↓

Phase 6

Integration

---

# Definition of Done

Income

CRUD

Search

Filter

Export

Timeline

Student Integration

Outstanding Update

Dashboard Update

Expense

CRUD

Dashboard Update

Timeline

Outstanding

Realtime Calculation

Dashboard

Realtime KPI

Realtime Chart

Realtime Statistics

---

Final Principle

Student owns business.

Finance owns money.

Dashboard owns visualization.

Each module has only one responsibility.