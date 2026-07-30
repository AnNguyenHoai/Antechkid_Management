# CENTER DESIGN SYSTEM

# 08. IMPLEMENTATION CONTRACT

Version: 1.0

Status: Mandatory

---

# Purpose

This document defines the implementation contract between

Design

and

Engineering.

Developers do not design.

Developers implement.

Design decisions belong to CDS.

Engineering decisions belong to implementation.

---

# Golden Rule

If CDS already defines a solution,

developers must use it.

Do not invent alternatives.

---

# Authority Order

When conflicts occur,

follow this priority.

1

Design Philosophy

↓

2

Page Templates

↓

3

Layout System

↓

4

Business Components

↓

5

Component Behaviors

↓

6

Content Language Guide

↓

7

Design Tokens

↓

8

Implementation

Implementation is always the last decision.

---

# Developers MUST NOT

Create new layouts.

Create new spacing.

Create new colors.

Create new typography.

Create new page templates.

Create new business components.

Create new interaction patterns.

Rename standard buttons.

Invent new icons.

Duplicate existing components.

Hard-code UI values.

---

# Developers MUST

Use existing Page Templates.

Use existing Business Components.

Use Design Tokens.

Use approved terminology.

Follow Component Behaviors.

Reuse Shared Components.

Preserve visual hierarchy.

Keep business workflow unchanged.

---

# Hard-coded Values

Forbidden

padding:17

margin:21

radius:11

width:237

height:53

Allowed

Space.LG

Radius.MD

Button.PRIMARY_HEIGHT

Sidebar.EXPANDED

---

# Page Construction

Every page

must begin by selecting a Page Template.

Never build pages from scratch.

Example

Student Detail

↓

Detail Template

↓

Student Summary

↓

Student Metrics

↓

Assessment

↓

Timeline

↓

Documents

---

# Component Construction

Pages

↓

Business Components

↓

Shared Components

↓

UI Components

↓

Design Tokens

Never skip layers.

---

# Layout Rules

Only one vertical scrollbar.

No nested scrolling.

No duplicated navigation.

No floating widgets without purpose.

No inconsistent spacing.

---

# Business Rules

Every user action

must update

Business Data

↓

Timeline

↓

Dashboard

↓

Analytics

↓

Notification

Manual refresh is prohibited.

---

# Naming Rules

Files

StudentSummaryCard

AssessmentCard

NeedAttentionCard

TimelineWidget

Never

Card1

Widget2

PanelNew

FrameTemp

---

# Code Organization

Workspace

↓

Pages

↓

Business Components

↓

Shared Components

↓

Infrastructure

Never mix business logic into UI files.

---

# Reusability Rule

If a UI appears

three times,

extract a component.

If a business workflow repeats,

extract a business component.

---

# Design Review

Engineering review

must answer

Did the code follow CDS?

Not

Does it look nice?

---

# Change Process

Developer

cannot modify CDS.

If CDS is insufficient

↓

Create Proposal

↓

Design Review

↓

Approve

↓

Update CDS

↓

Implement

Never bypass CDS.

---

# Exceptions

Temporary exceptions require

Reason

Owner

Removal Plan

Deadline

Permanent exceptions are not allowed.

---

# Definition of Done

A feature is complete only when

✓ Correct Page Template

✓ Correct Business Components

✓ Correct Design Tokens

✓ Correct Language

✓ Correct Behavior

✓ Correct Workflow

✓ Correct Layout

Passing tests alone is insufficient.

---

# Developer Checklist

Before merging code

confirm

□ No hard-coded spacing

□ No duplicated layouts

□ Correct template

□ Correct business components

□ Correct terminology

□ Correct interactions

□ Correct empty state

□ Correct loading state

□ Correct error state

□ Correct accessibility

---

# Review Checklist

Every Pull Request

must reference

Affected Page Template

Affected Business Components

Affected Shared Components

Affected Tokens

Affected Behaviors

Affected Workflows

PRs without CDS references

should not be approved.

---

# Final Principle

Developers build software.

CDS builds the product.

The responsibility of Engineering

is not to invent UI,

but to implement the product consistently.