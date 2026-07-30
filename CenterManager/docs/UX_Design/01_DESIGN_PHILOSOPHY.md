# CENTER DESIGN SYSTEM

# 01. DESIGN PHILOSOPHY

Version: 1.0

Status: Draft

---

# Purpose

Center Design System (CDS) defines the visual language, interaction principles, layout rules, and reusable components used throughout the CenterManager platform.

Every Workspace must follow CDS.

Developers should implement the system instead of inventing new UI.

---

# Design Goal

CenterManager is not designed to impress users with visual effects.

It is designed to help education center staff complete daily work quickly, accurately, and with minimum cognitive load.

The interface should disappear behind the workflow.

Users should think about students—not about the software.

---

# Core Principles

## 1. Business First

Every screen must support a business task.

Never add UI that exists only for decoration.

Question before adding anything:

"What business problem does this solve?"

---

## 2. Information Before Decoration

Hierarchy is more important than colors.

Spacing is more important than borders.

Typography is more important than shadows.

Users should immediately know

- where they are
- what is important
- what action comes next

---

## 3. Consistency Over Creativity

Every Workspace should feel familiar.

If a user knows Student Workspace,

they should already know how Teacher Workspace works.

Consistency is preferred over originality.

---

## 4. One Responsibility Per Screen

Every screen answers one question.

Dashboard

"What needs attention today?"

Student List

"Which student do I want to manage?"

Student Detail

"Everything about this student."

Analytics

"How is the business performing?"

Never mix responsibilities.

---

## 5. Reduce Cognitive Load

The interface should require as little thinking as possible.

Avoid

- duplicated navigation
- repeated information
- unnecessary buttons
- excessive options

The best UI is often the simplest one.

---

## 6. Progressive Disclosure

Show only what users need now.

Advanced information should appear only when required.

Examples

Dashboard

↓

Summary

Student Detail

↓

Complete Information

Analytics

↓

Historical Data

---

## 7. Reuse Everything

Every button

Every card

Every table

Every dialog

Every toolbar

should come from the Component Library.

Never redesign an existing component.

---

## 8. Workflow Driven

CenterManager is a workflow system.

Not a CRUD system.

Example

Assessment Created

↓

Timeline Updated

↓

Dashboard Updated

↓

Analytics Updated

↓

Notification Generated

The workflow is the product.

---

## 9. Data Over Decoration

Charts exist to support decisions.

Cards exist to summarize information.

Icons exist to improve recognition.

Nothing exists only because it looks nice.

---

## 10. Invisible Design

The best compliment for the interface is

"I finished my work quickly."

Not

"The UI looks beautiful."

Beauty comes from clarity.

---

# Product Identity

CenterManager should feel

Professional

Reliable

Predictable

Efficient

Calm

The interface should never feel

Playful

Flashy

Distracting

Experimental

---

# Design Inspiration

The following products are used as references.

Navigation

Microsoft Dynamics 365

Entity Detail

HubSpot CRM

Data Tables

Airtable

Analytics

Power BI

Interaction Simplicity

Notion

Component Consistency

Fluent Design

These products inspire the interaction model.

They are not copied visually.

---

# CDS Rule

Developers should never ask

"How should I design this?"

Instead ask

"Which CDS pattern already solves this?"

If no pattern exists,

the Design System should evolve first.

The application comes second.