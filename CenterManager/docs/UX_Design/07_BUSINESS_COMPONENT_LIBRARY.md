# CENTER DESIGN SYSTEM

# 07. BUSINESS COMPONENT LIBRARY

Version: 1.0

Status: Approved

---

# Purpose

Business Components are reusable business building blocks.

Unlike UI Components,

Business Components already understand business meaning.

Developers should assemble pages using Business Components,

not individual UI controls.

---

# Business Component Hierarchy

Business Components

↓

Composite Components

↓

UI Components

↓

Design Tokens

Example

Student Detail

↓

Student Summary Card

↓

Avatar

Text

Badge

Button

↓

Spacing

Typography

Color

Radius

---

# Student Components

## Student Summary Card

Purpose

Display essential student information.

Contains

Avatar

Student Name

Student ID

Status

Course

Grade

Age

Primary Contact

Quick Actions

Never

Assessment

Timeline

Documents

Those belong to other components.

---

## Student Metrics Card

Purpose

Display student KPIs.

Contains

Attendance Rate

Average Assessment Score

Completed Courses

Last Assessment

Never

Editable data.

Metrics are read-only.

---

## Parent Information Card

Purpose

Display parent information.

Contains

Primary Contact

Relationship

Phone

Email

Address

Emergency Contact

Quick Call

Quick Email

---

## Assessment Summary Card

Purpose

Provide assessment overview.

Contains

Latest Score

Previous Score

Improvement

Trend

Status

Quick Action

View Assessment

---

## Timeline Component

Purpose

Display student history.

Contains

Date

Time

Event

Description

Actor

Rules

Newest first.

Grouped by time.

No raw system events.

---

## Document Component

Purpose

Display related documents.

Contains

File Icon

Name

Category

Size

Upload Date

Actions

Download

Preview

Delete

---

## Student Activity Card

Purpose

Display recent activities.

Contains

Latest Timeline Events.

Maximum

10 items.

View All button.

---

# Dashboard Components

## Need Attention Card

Purpose

Display urgent work.

Priority

Critical

High

Normal

Maximum

5 items.

Every item clickable.

---

## Today's Summary Card

Purpose

Provide today's operational snapshot.

Contains

New Students

Today's Classes

Pending Payments

Pending Assessments

---

## Recent Activity Card

Purpose

Display latest business events.

Grouped by

Time

Entity

Never show technical logs.

---

## Upcoming Events Card

Purpose

Display upcoming business events.

Examples

Assessment

Birthday

Course Start

Payment Due

---

## Quick Insight Card

Purpose

Provide small analytical highlights.

Maximum

4 metrics.

Never replace Analytics.

---

# Analytics Components

## KPI Card

Purpose

Display one KPI.

Contains

Value

Trend

Delta

Description

Never

Buttons

Editable content

---

## Trend Chart

Purpose

Show change over time.

Contains

Title

Legend

Chart

Summary

---

## Distribution Chart

Purpose

Display category distribution.

Contains

Chart

Legend

Percentage

---

## Comparison Card

Purpose

Compare two business values.

Examples

Current Month

vs

Last Month

---

# Teacher Components

Teacher Summary

Teacher Schedule

Teaching Metrics

Assigned Classes

Availability

Teacher Timeline

Future Workspace.

---

# Finance Components

Invoice Summary

Payment Status

Revenue Card

Outstanding Payment

Cash Flow Summary

Future Workspace.

---

# Shared Components

Metric Card

Status Card

Activity Card

Timeline

Entity Header

Search Toolbar

Filter Panel

Pagination

Empty State

Notification

These components are shared by every Workspace.

---

# Business Component Rules

Every page should be composed of Business Components.

Never directly assemble pages using Buttons and Labels.

Bad

Button

Label

Frame

Layout

Good

Student Summary Card

Assessment Card

Timeline Component

Metric Card

---

# Evolution Rule

If three Workspaces build similar business content,

extract a new Business Component.

Never duplicate business layouts.

---

# Review Checklist

Every review verifies

✓ Correct Business Component selected

✓ Business responsibility is clear

✓ No duplicated components

✓ Correct composition

✓ Reusable

✓ Consistent with CDS

Business Components are the foundation of every Workspace.