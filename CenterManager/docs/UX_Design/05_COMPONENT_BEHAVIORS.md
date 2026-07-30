# CENTER DESIGN SYSTEM

# 05. COMPONENT BEHAVIORS

Version: 1.0

Status: Approved

---

# Purpose

This document defines how every component behaves.

It does not define appearance.

Appearance belongs to Design Tokens.

Structure belongs to Layout System.

Behavior belongs here.

Users remember behavior more than colors.

---

# General Principles

Every component should behave consistently.

Users should never need to guess.

Hover

Click

Focus

Disabled

Loading

Error

must always behave identically.

---

# Button

States

Default

Hover

Pressed

Disabled

Loading

Rules

Hover

Slight elevation

Pressed

Slightly darker

Loading

Spinner replaces icon

Disabled

Cannot receive focus

---

# Search Box

Typing immediately updates local filtering.

Global search requires

Enter

or

Search Button.

Escape clears search.

Search always remembers previous keyword.

---

# Table

Single Click

Select row.

Double Click

Open Detail.

Right Click

Context Menu.

Checkbox

Multi-select.

Ctrl

Multi-selection.

Shift

Range selection.

---

# Pagination

Changing page

Never resets filters.

Never resets sorting.

Never resets search.

---

# Filter

Filters remain active until removed.

Closing the page should remember filters.

Users should not need to recreate filters repeatedly.

---

# Sorting

Sorting survives

Refresh

Pagination

Filtering

until explicitly changed.

---

# Dialog

ESC

Close

Outside Click

Optional

Save

Closes only when successful.

Validation errors never close the dialog.

---

# Form

Unsaved changes

↓

Warn before closing.

Invalid field

↓

Focus automatically.

First error

↓

Scroll into view.

---

# Tabs

Changing tabs

Never loses data.

Unsaved changes

↓

Confirmation.

Current tab

Always highlighted.

---

# Timeline

Newest first.

Automatically refresh after business events.

Never require manual reload.

---

# Dashboard Widgets

Refresh automatically.

No page refresh required.

Loading

Skeleton

Never blank.

---

# Charts

Loading

Skeleton.

No Data

Empty State.

Error

Retry.

---

# Notifications

Success

Auto-hide

3 seconds.

Warning

Manual dismiss.

Error

Manual dismiss.

Never stack more than

3 notifications.

---

# Empty State

Every Empty State must contain

Illustration

↓

Title

↓

Description

↓

Primary Action

Never display

"No Data"

alone.

---

# Loading

Every page

Skeleton.

Every table

Skeleton.

Every card

Skeleton.

Never freeze UI.

---

# Error Handling

Technical errors

Hidden.

Business errors

Readable.

Example

Bad

SQL Error

Good

Unable to save student information.

Please try again.

---

# Keyboard

Tab

Next Field.

Shift Tab

Previous.

Enter

Primary Action.

ESC

Cancel.

---

# Focus

Every interactive control

must display

Focus State.

Keyboard users must always know

where focus is.

---

# Scroll

Mouse Wheel

Natural.

Touchpad

Natural.

Keyboard

Supported.

Never scroll two panels simultaneously.

---

# Business Refresh Rules

Creating Assessment

↓

Timeline

↓

Dashboard

↓

Analytics

↓

Notification

Creating Parent

↓

Timeline

↓

Dashboard

↓

Student Detail

No manual refresh.

---

# Consistency Rule

If two buttons perform the same action,

they must behave identically.

If two tables display data,

they must behave identically.

Behavior consistency is mandatory.

---

# Review Checklist

Review every component.

✓ Hover

✓ Focus

✓ Disabled

✓ Loading

✓ Empty

✓ Error

✓ Keyboard

✓ Refresh

✓ Selection

✓ Accessibility

Behavior inconsistencies are defects.