# UI-PROD-06 — Form & Detail UX

## Goal

Standardize the operational experience for editing and reviewing records without
moving validation, permissions, collaboration ownership, or domain rules into UI
components. UI-PROD-06 adds a reusable Form/Detail pattern layer above Design System
V2 foundation controls and migrates the Student form plus core Student detail
surfaces as the representative implementation.

## Interaction model

A Form/Detail screen should compose these layers:

1. application/workspace shell from UI-PROD-03;
2. page-local detail actions with explicit edit/read-only state;
3. compact form or detail sections with clear visual hierarchy;
4. canonical foundation controls for common inputs/actions;
5. inline field validation where the user can act on it;
6. service/domain validation as the authoritative business rule;
7. collaboration and permission ownership outside the visual components.

The UI may explain whether editing is enabled, but it never decides whether the
user owns the write session.

## Form/Detail pattern layer

`centermanager.ui.design_system.form_detail` introduces five reusable primitives:

- `FormField`: label, required marker, helper copy, and inline validation message;
- `FormSection`: compact grouping for related fields;
- `DetailRow`: consistent read-only label/value hierarchy;
- `DetailSection`: quiet bordered section for operational details;
- `EditStateBanner`: explicit `readonly`, `editing`, and `locked` feedback.

These patterns are domain-neutral. They do not import services, repositories,
permissions, or collaboration managers.

## Form validation contract

`FormField` can wrap any QWidget. When the wrapped control exposes `set_error`, the
validation state is propagated to that control. Otherwise the field still owns the
inline message and exposes a semantic `validationState` property on the control.

This creates one presentation contract without replacing service validation.
Business validation remains authoritative and may continue to raise domain/service
exceptions.

## Representative migration — Student Form

`StudentFormDialog` keeps its existing public and service-facing contract while the
presentation is migrated to V2:

- `full_name_edit`, `preferred_name_edit`, `dob_edit`, `gender_combo`, `level_edit`,
  `notes_edit`, `save_btn`, `cancel_btn`, and date-null behavior remain available;
- common text/select/action controls now use `Input`, `Select`, and `Button`;
- fields are grouped in a `FormSection` and represented by `FormField`;
- service `StudentValidationError` still controls business validation and is now
  also surfaced inline at the primary required field;
- no repository, model, or service signature is changed.

## Representative migration — Student Detail

The core Student detail presentation is migrated incrementally without rewriting
its business-heavy parent page:

- `ProfileWidget` composes a `DetailSection` and `DetailRow` cells;
- the existing identity, status, image, guardian, and learning information remains;
- image fallback is text/initial based rather than emoji based;
- `QuickActionsWidget` uses canonical `Button` controls;
- `QuickActionsWidget.set_write_enabled()` continues to receive the write decision
  from `StudentDetailPage`, while `EditStateBanner` only communicates that state;
- read-only PDF export remains enabled exactly as before;
- existing action signal/callback contracts are preserved.

The larger Student Detail parent still owns loading, child services, permission
checks, write guards, tab wiring, and refresh behavior. Broader cosmetic migration
of all nested Student sub-sections remains an incremental workspace migration task,
not a reason to duplicate or move their domain logic here.

## Visual rules

Migrated UI-PROD-06 sources:

- consume colors, type, radius, spacing and borders from Design System V2 tokens;
- do not contain raw hexadecimal colors;
- do not use emoji as UI icon language;
- do not add `centermanager.ui.styles` dependencies;
- favor bordered, low-elevation sections over card-heavy presentation;
- retain text-first controls that remain clear at desktop scaling.

## Scope guard

Not changed in UI-PROD-06:

- repositories/database models;
- Student service create/update signatures;
- permission definitions;
- collaboration/write-lock ownership rules;
- Student Detail service wiring and refresh flow;
- Finance visibility rules;
- application routing;
- global feedback architecture reserved for UI-PROD-07.

## Verification

Run from `CenterManager`:

```bash
python -m pytest tests/test_form_detail_ux_v2.py
python -m pytest tests/test_component_foundation_v2.py
python -m pytest tests/test_design_system_tokens.py
python -m pytest
```

The Windows full pytest workflow remains the merge gate.

## Acceptance criteria

- one reusable Form/Detail pattern layer exists above foundation controls;
- field validation is visible inline without owning business validation rules;
- detail label/value hierarchy is reusable across workspaces;
- edit/read-only state is explicit but write ownership remains platform-owned;
- Student Form demonstrates the form pattern without service changes;
- Student Profile and Quick Actions demonstrate the detail pattern while preserving
  existing public contracts;
- PDF export remains available in read-only mode;
- migrated sources contain no raw colors, emoji literals, or new `ui.styles` usage;
- full pytest remains the merge gate.

## Follow-up

UI-PROD-07 can standardize application feedback/state behavior on top of the same
semantic state vocabulary. UI-PROD-08 can then migrate Teacher, Class, Finance,
Employee, Admin, and remaining Student detail sections without copying form/detail
QSS or domain logic.
