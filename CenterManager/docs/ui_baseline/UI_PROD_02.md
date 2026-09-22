# UI-PROD-02 — Component Foundation V2

## Purpose

UI-PROD-02 turns Design System V2 from a token contract into a reusable
production component layer. It standardizes the low-level controls that later
workspace migrations can assemble without redefining colors, typography,
spacing, radii, elevation or interaction states.

Base revision:

`53297373985fa87e59832275f8efb225cc4e8319`

That revision is the merge of UI-PROD-01 into `main_repos`.

## Architecture

```text
Workspace / Page
      |
      v
Shared / Domain Patterns
      |
      v
ui.design_system.foundation
      |
      v
ui.design_system.theme
      |
      v
ui.design_system.tokens
```

`tokens.py` remains the only owner of visual values.

## Canonical components

| Component | Responsibility |
| --- | --- |
| `Button` | Primary/accent/secondary/danger/ghost actions; sm/md/lg sizes |
| `Input` | Text input, clear affordance and validation/error state |
| `Select` | Combo/select with semantic focus, disabled and error states |
| `Badge` | Compact status/tone presentation |
| `Card` | Standard bordered/elevated content surface |
| `Toolbar` | Start/end zones and standard action placement |
| `Tabs` | Page-local navigation with consistent selected/hover/disabled states |
| `Dialog` | Modal shell with title, body and standardized footer actions |
| `EmptyState` | No-content presentation and optional recovery/action |
| `LoadingState` | Indeterminate loading or skeleton rows |
| `ErrorState` | Recoverable error presentation with retry action |
| `Skeleton` | Token-driven loading placeholder |

The public package exports these names from
`centermanager.ui.design_system`.

## Component geometry tokens

UI-PROD-02 adds two token-owned dictionaries:

- `CONTROL_SIZES`
  - small, medium and large control height/padding/font size;
- `COMPONENT_METRICS`
  - border width, badge height, toolbar height, tab geometry, dialog minimum
    width, state-view width and loading/skeleton geometry.

These live in `tokens.py`; `foundation.py` contains no raw hexadecimal colors.

## Interaction contracts

### Button

Use one of:

- `primary` — default high-emphasis product action;
- `accent` — AnTech orange accent action, intentionally used selectively;
- `secondary` — neutral supporting action;
- `danger` — destructive action;
- `ghost` — low-emphasis chrome/action.

Disabled, hover, pressed and focus styles resolve from semantic Design System
tokens.

### Input / Select

Both expose:

```python
control.set_error("Human-readable validation message")
control.clear_error()
```

Error state affects the border and tooltip without requiring local QSS.

### Badge

For generic meaning, use a semantic tone. For domain status values already in
`BADGE_COLORS`, use:

```python
Badge.from_status("ACTIVE")
```

### Card

Use `elevation="none" | "sm" | "md" | "lg"`. Elevation uses
`QGraphicsDropShadowEffect` and the token-owned elevation specification.

### Dialog

Content is added through `body_layout` or `add_body_widget()`. Primary and
cancel buttons are provided by the component rather than recreated per dialog.

## Shared compatibility layer

The existing shared UI namespace already had separate `EmptyState` and loading
implementations. UI-PROD-02 removes that styling duplication while preserving
imports:

- `ui.shared.empty_state.EmptyState` now points to the canonical component;
- `ui.shared.loading_widget.LoadingSkeleton` wraps canonical `Skeleton`;
- `ui.shared.loading_widget.LoadingWidget(count=...)` remains callable and is
  backed by canonical `LoadingState`;
- `ui.shared.error_state.ErrorState` is added as the canonical error state.

Legacy business-facing components in `design_system/components.py` are not
rewritten in this task. They remain exported for compatibility and will be
retired/migrated incrementally in later UI-PROD work.

## Usage

```python
from centermanager.ui.design_system import (
    Badge,
    Button,
    ButtonVariant,
    Card,
    EmptyState,
    ErrorState,
    Input,
    Select,
    Tabs,
    Toolbar,
)

toolbar = Toolbar()
toolbar.add_widget(Input("Search students"))
toolbar.add_widget(Select(["Active", "Inactive"]))
toolbar.add_action("Add student", variant=ButtonVariant.PRIMARY)

card = Card("Student profile", "Core information")
card.add_widget(Badge.from_status("ACTIVE"))
```

## Scope guard

UI-PROD-02 does not:

- migrate every workspace/page to the new components;
- redesign navigation or the application shell;
- change table behavior;
- change business logic, services or persistence;
- remove legacy component exports required by existing screens.

Those migrations are deliberately separated so visual regressions remain
reviewable.

## Verification

```bash
cd CenterManager
python -m pytest tests/test_component_foundation_v2.py
python -m pytest tests/test_design_system_tokens.py
python -m pytest tests/test_ui_inventory_tool.py
```

The full repository pytest suite remains the merge gate.

## Acceptance criteria

- [x] Button foundation has semantic variants and standard sizes.
- [x] Input and Select share focus/disabled/error behavior.
- [x] Badge uses semantic tones and existing status mappings.
- [x] Card uses standard surface/border/radius/elevation.
- [x] Toolbar has predictable start/end action zones.
- [x] Tabs have standard hover/selected/disabled states.
- [x] Dialog supplies a consistent modal shell and footer.
- [x] Empty, Loading and Error states are standardized.
- [x] Existing shared Empty/Loading imports remain compatible.
- [x] Foundation contains no raw hexadecimal color values.
- [x] Component geometry is owned by Design System tokens.
- [x] Automated contract tests cover the component foundation.
