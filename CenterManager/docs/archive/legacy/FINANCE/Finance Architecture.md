# Finance Architecture
Version: 1.0
Status: Approved

---

# 1. Purpose

Finance Module is responsible for managing all financial activities inside CenterManager.

Its responsibilities are:

- Record income
- Record expense
- Calculate outstanding tuition
- Generate dashboard statistics

Finance is an Administration Module.

It is NOT the center of business operations.

Business operations always begin from Student.

---

# 2. Architecture Overview

                    +----------------+
                    |    Student     |
                    +----------------+
                            |
                            |
                    Collect Tuition
                            |
                            ▼
                    +----------------+
                    |     Income     |
                    +----------------+
                            |
             +--------------+--------------+
             |                             |
             ▼                             ▼
    Outstanding Service          Dashboard Service
             |                             |
             ▼                             ▼
 Student Financial Tab         Finance Dashboard

--------------------------------------------------

                    +----------------+
                    |    Expense     |
                    +----------------+
                            |
                            ▼
                   Dashboard Service

---

# 3. Module Responsibility

## Student Module

Responsible for

- Student information
- Courses
- Enrollment
- Tuition definition

Student NEVER calculates finance.

---

## Finance Module

Responsible for

- Income
- Expense
- Financial reports

Finance NEVER stores student profile.

Only references Student ID.

---

## Dashboard Module

Responsible only for visualization.

Dashboard NEVER stores data.

Dashboard NEVER owns business logic.

---

# 4. Data Ownership

Student

owns

- Student Profile
- Registered Courses
- Tuition Fee

Finance

owns

- Income
- Expense

Outstanding Service

owns

- Outstanding Calculation

Dashboard

owns

- KPI Visualization

---

# 5. Data Flow

Student Detail

↓

Financial Tab

↓

Collect Tuition

↓

Income Record Created

↓

Outstanding Service

↓

Dashboard Service

↓

Timeline Service

↓

UI Updated

---

# 6. Income Flow

User clicks

Collect Tuition

↓

Validate Student

↓

Validate Amount

↓

Create Income Record

↓

Update Timeline

↓

Recalculate Outstanding

↓

Refresh Dashboard

↓

Success

---

# 7. Expense Flow

Finance

↓

Create Expense

↓

Validate

↓

Save Expense

↓

Refresh Dashboard

↓

Success

---

# 8. Outstanding Flow

Outstanding is NOT stored.

Outstanding is calculated.

Formula

Outstanding

=

Expected Tuition

-

Total Paid

Expected Tuition

comes from

Student Course

Paid

comes from

Income

---

# 9. Dashboard Flow

Dashboard reads

Income

Expense

Outstanding

Dashboard calculates

Revenue Today

Revenue Month

Expense Today

Expense Month

Current Balance

Outstanding Tuition

Dashboard NEVER updates database.

---

# 10. Timeline Flow

Income

↓

Student Timeline

Expense

↓

System Timeline

Examples

Paid Tuition

Bought Equipment

Refund Tuition

Salary Payment

---

# 11. Database Design

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

No table

Outstanding

Dashboard

Statistics

These are calculated.

---

# 12. Service Layer

FinanceService

Responsible for

CRUD

IncomeService

Responsible for

Income CRUD

ExpenseService

Responsible for

Expense CRUD

OutstandingService

Responsible for

Outstanding Calculation

DashboardService

Responsible for

Dashboard KPI

TimelineService

Responsible for

Timeline Generation

---

# 13. Dependency

Student

↓

Income

↓

Outstanding

↓

Dashboard

Timeline

Dashboard never calls Student directly.

Dashboard only reads services.

---

# 14. Permission Architecture

Teacher

×

Finance

Reception (Future)

Collect Tuition Only

Admin

Full Finance Access

Permissions

finance.view

finance.income.create

finance.income.update

finance.income.delete

finance.expense.create

finance.expense.update

finance.expense.delete

---

# 15. Security

Permission must be verified

Frontend

AND

Backend

Never trust frontend.

API always validates permission.

Unauthorized request

↓

403 Forbidden

---

# 16. Error Handling

Student Not Found

↓

404

Invalid Amount

↓

400

Permission Denied

↓

403

Unexpected Error

↓

500

---

# 17. Performance

Dashboard

Response

< 1 second

Income Search

< 500 ms

Expense Search

< 500 ms

Outstanding Calculation

Realtime

---

# 18. Future Extension

Finance Architecture supports

Multiple Branches

Multiple Currencies

Discount

Scholarship

Refund

Invoice

Payroll

Without redesign.

---

# 19. Design Principles

Single Responsibility

One module owns one responsibility.

No duplicated data.

Everything has one owner.

Dashboard is read-only.

Outstanding is calculated.

Finance is administration.

Student is business center.

---

# 20. Architecture Rules

DeepSeek MUST follow these rules.

Rule 1

Never redesign architecture.

Rule 2

Never duplicate data.

Rule 3

Never store calculated values.

Rule 4

Dashboard is visualization only.

Rule 5

Business starts from Student.

Rule 6

Finance stores transactions only.

Rule 7

Every transaction updates Timeline.

Rule 8

Every API validates permission.

Rule 9

Every calculation belongs to Service Layer.

Rule 10

When uncertain, stop implementation and report instead of making assumptions.