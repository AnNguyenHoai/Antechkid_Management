# TEACHER-2.5 — Workspace UX & Data Consistency Audit

## Scope

Final audit pass over Teacher Workspace after TEACHER-2.0 through 2.4.

## Findings and fixes

### 1. Duplicate workspace signal connections

`TeacherWorkspaceShell` connected navigation/header signals during `_setup_ui()` and
again through `_connect_signals()`.

**Fix:** keep one connection path only.

### 2. Cross-page refresh did not include visible Teacher Detail

List and Dashboard refreshed after mutations, but an already-open detail could
remain stale.

**Fix:** `_refresh_teacher_views()` now refreshes List, Dashboard, and reloads
the current Detail aggregate when Detail is visible.

### 3. Archived teachers displayed their old business status

An archived teacher could still appear as `Active` or `Inactive` in the list.

**Fix:** archived rows now display the lifecycle state `ARCHIVED`.

### 4. Archived mode allowed irrelevant controls

The Add action and Assignment filter remained available while viewing archived
records.

**Fix:** Archived mode disables those controls. WRITE mode cannot re-enable Add
or Bulk Archive while Archived is selected.

## Result

Teacher Workspace now has a single navigation signal path, synchronized read
models, explicit archived lifecycle display, and context-aware list controls.
