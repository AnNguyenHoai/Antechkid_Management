# CENTER DESIGN SYSTEM

# 03. LAYOUT SYSTEM

Version: 1.0

Status: Approved

---

# Purpose

Layout defines how information is organized on every screen.

Layout is more important than components.

Good layout reduces cognitive load.

Poor layout cannot be fixed by better colors or better icons.

---

# Philosophy

CenterManager follows

"Scan First, Read Second"

Users should understand

• where they are

• what is important

• what action comes next

within 3 seconds.

---

# Visual Hierarchy

Every page follows exactly four levels.

Level 1

Page Identity

Example

Student Detail

Teacher Dashboard

Finance Workspace

---

Level 2

Primary Actions

Add

Edit

Export

Import

Search

Filter

---

Level 3

Business Information

Cards

Tables

Charts

Timeline

Forms

---

Level 4

Supporting Information

Notes

Description

Metadata

Statistics

History

---

Never reverse this hierarchy.

---

# Page Width

Content must breathe.

Never stretch content across the entire screen.

Recommended

Content Width

1200~1440 px

Maximum

1600 px

Ultra-wide monitors

Center content.

Never let a table stretch to 3000 pixels.

---

# Page Margin

Left

24

Right

24

Top

24

Bottom

24

Always use Design Tokens.

---

# Vertical Rhythm

Every page follows

24 px

between sections.

Example

Header

↓

24

↓

Toolbar

↓

24

↓

Content

↓

24

↓

Footer

Never use inconsistent spacing.

---

# Page Structure

Every Workspace page follows

Page Header

↓

Toolbar

↓

Main Content

↓

Secondary Content (optional)

↓

Footer (optional)

Never skip the Header.

---

# Header Layout

Contains

Title

Subtitle (optional)

Primary Actions

Never place filters inside Header.

---

# Toolbar Layout

Toolbar contains

Search

Filter

Sort

Export

Bulk Actions

Toolbar is the operational area.

---

# Dashboard Layout

Dashboard is an operational cockpit.

Order is fixed.

Today's Summary

↓

Need Attention

↓

Upcoming Events

↓

Recent Activities

↓

Quick Insights

Never place charts above Need Attention.

Operational information always comes first.

---

# List Page Layout

Student List

Teacher List

Course List

always follows

Header

↓

Toolbar

↓

Table

↓

Pagination

Filters never appear below the table.

---

# Detail Page Layout

Every Detail page follows

Entity Header

↓

Summary

↓

Statistics

↓

Main Tabs

↓

Business Content

Example

Student Header

↓

Student Summary

↓

Metrics

↓

Tabs

↓

Assessment

↓

Timeline

↓

Documents

Never place Timeline above Summary.

---

# Form Layout

Every Form

General Information

↓

Business Information

↓

Advanced Information

↓

Danger Zone

Save button always appears at the bottom right.

Cancel always appears left of Save.

---

# Dialog Layout

Dialog

Title

↓

Description

↓

Content

↓

Actions

Buttons always aligned right.

Primary action on the far right.

---

# Card Layout

Card

Header

↓

Content

↓

Footer (optional)

Do not mix Header and Content.

---

# Table Layout

Table

Toolbar

↓

Header

↓

Rows

↓

Pagination

Actions belong to the last column.

Checkbox belongs to the first column.

---

# Analytics Layout

Analytics always follows

Filters

↓

KPIs

↓

Trend Charts

↓

Distribution Charts

↓

Detail Table

Never mix dashboard widgets into Analytics.

---

# Timeline Layout

Timeline

Newest first.

Group by

Today

Yesterday

This Week

Earlier

Never display raw system events.

Example

❌

ParentUpdated

✓

Primary Contact Updated

---

# Empty Layout

When there is no data

Illustration

↓

Title

↓

Description

↓

Primary Action

Never leave blank space.

---

# Alignment Rules

All page elements align to the same vertical grid.

Never

Shift cards by a few pixels.

Never

Center one section while left-aligning another.

Alignment errors are considered layout defects.

---

# White Space Rules

White space is intentional.

Do not fill empty space with more widgets.

Empty space improves readability.

---

# Responsive Rules

Compact

Hide secondary panels.

Wide

Two-column layout.

Ultra-wide

Limit content width.

Never stretch information.

---

# Scroll Rules

Only one vertical scrollbar per page.

Nested scrolling is prohibited.

Horizontal scrolling is allowed only for large tables.

Cards must never have independent scrollbars unless they contain long content.

---

# Layout Review Checklist

Every page review should verify

✓ One primary scrollbar

✓ Correct hierarchy

✓ Consistent spacing

✓ Proper alignment

✓ Predictable structure

✓ Comfortable reading width

✓ No duplicated navigation

✓ Business-first information order

If any rule is violated,

the layout is considered incorrect regardless of visual appearance.