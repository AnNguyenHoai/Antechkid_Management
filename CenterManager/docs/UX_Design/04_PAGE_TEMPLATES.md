# CENTER DESIGN SYSTEM

# 04. PAGE TEMPLATES

Version: 1.0

Status: Approved

---

# Purpose

Page Templates define the standard structure of every screen in CenterManager.

Developers should never invent a new page layout.

Every page must reuse an existing template.

If a suitable template does not exist,

create the template first.

Then build the page.

---

# Available Templates

CenterManager currently defines

• Dashboard Page

• List Page

• Detail Page

• Analytics Page

• Form Page

• Wizard Page

• Settings Page

Every Workspace must reuse these templates.

---

# Template 1

Dashboard Page

Purpose

Operational overview.

Question answered

"What requires my attention today?"

Structure

Page Header

↓

Today's Summary

↓

Need Attention

↓

Upcoming Events

↓

Recent Activities

↓

Quick Insights

Rules

Operational information always appears before analytical information.

Charts never appear above Need Attention.

No CRUD forms.

No editable data.

Dashboard is read-first.

---

# Template 2

List Page

Purpose

Browse and locate business entities.

Question answered

"What record am I looking for?"

Structure

Page Header

↓

Toolbar

↓

Table

↓

Pagination

Toolbar contains

Search

Filter

Sort

Export

Bulk Actions

Rules

Table occupies the largest area.

Actions are always outside the table except row actions.

No charts.

No timeline.

---

# Template 3

Detail Page

Purpose

Manage one business entity.

Question answered

"Everything about this entity."

Structure

Entity Header

↓

Summary Card

↓

Metrics

↓

Tabs

↓

Business Content

Example

Student

↓

Overview

↓

Parents

↓

Assessment

↓

Timeline

↓

Documents

Rules

Timeline is never shown before Summary.

Summary is always visible.

Tabs separate responsibilities.

---

# Template 4

Analytics Page

Purpose

Support decision making.

Question answered

"How is the business performing?"

Structure

Filters

↓

KPI Cards

↓

Trend Charts

↓

Distribution Charts

↓

Detail Table

Rules

Dashboard widgets are prohibited.

Analytics never contains editing actions.

Charts are primary.

Tables support charts.

---

# Template 5

Form Page

Purpose

Create or edit information.

Structure

Header

↓

General Information

↓

Business Information

↓

Advanced Settings

↓

Danger Zone (optional)

↓

Actions

Rules

Fields grouped logically.

Labels aligned.

Primary button

Save

Secondary button

Cancel

---

# Template 6

Wizard Page

Purpose

Guide users through a multi-step workflow.

Structure

Title

↓

Progress Indicator

↓

Current Step

↓

Navigation Buttons

Rules

Maximum

7 steps

Previous

Left

Next

Right

Finish

Right

Never skip progress indicator.

---

# Template 7

Settings Page

Purpose

Configure system behavior.

Structure

Category Navigation

↓

Setting Groups

↓

Individual Settings

↓

Save

Rules

Never use tabs inside settings.

Group related settings.

Explain every option.

---

# Page Selection Guide

Need operational overview?

Dashboard

Need many records?

List

Need one entity?

Detail

Need charts?

Analytics

Need data entry?

Form

Need guided process?

Wizard

Need configuration?

Settings

---

# Workspace Mapping

Home

Dashboard Template

Student Workspace

Dashboard

Student List

Student Detail

Analytics

Teacher Workspace

Dashboard

Teacher List

Teacher Detail

Analytics

Finance Workspace

Dashboard

Invoice List

Invoice Detail

Analytics

Future Workspaces must reuse the same templates.

---

# Forbidden Patterns

Dashboard mixed with Analytics.

List mixed with Forms.

Detail without Summary.

Analytics without Filters.

Multiple templates inside one page.

If two templates appear together,

the page should be split.

---

# Review Checklist

Every page review verifies

✓ Correct template selected

✓ Template structure unchanged

✓ Required sections present

✓ No forbidden sections

✓ Consistent navigation

✓ Predictable user flow

Pages failing these checks should be redesigned before implementation.