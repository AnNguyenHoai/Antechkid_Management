# EP-PROTOTYPE-09 — Student Timeline

## Purpose
Freeze the P9 Student Timeline operational contract using the existing Student Workspace and TimelineService implementation.

## Operational flow

Student Workspace → open a student → Profile → Timeline → review chronological activity.

## Required scope

- Student detail exposes a Timeline section inside the Profile surface.
- Timeline data is loaded for the currently selected student.
- Timeline events are rendered as read-only timeline cards.
- Empty timelines have an explicit empty state.
- Timeline retrieval remains owned by `TimelineService`; the UI does not create repositories or sessions.
- Timeline events are persisted through the existing repository/service boundary.

## Boundary contract

- `StudentDetailPage` coordinates the student detail presentation and delegates timeline retrieval to `TimelineService`.
- `TimelineService` owns timeline persistence and retrieval.
- `TimelineWidget` renders events and does not own persistence.
- `TimelineCard` is read-only presentation of one event.
- No new Timeline router, repository, service, or parallel event store is introduced.

## Non-goals

- No redesign of the existing timeline UI.
- No new event types or migration of existing timeline data.
- No filtering/search redesign.
- No write/edit/delete controls in the Student Timeline surface.

## Completion gate

1. Targeted EP-PROTOTYPE-09 regression tests pass.
2. Full regression suite passes.
3. No production behavior change is required unless the audit identifies a concrete defect.
