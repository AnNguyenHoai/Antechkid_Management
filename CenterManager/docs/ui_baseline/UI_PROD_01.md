# UI-PROD-01 — Design System V2

## Goal

Establish **one source of truth** for CenterManager visual values before the component and workspace migrations begin.

UI-PROD-01 owns only the foundation:

- color;
- typography;
- spacing;
- radius;
- elevation;
- interaction/status state.

It does not redesign screens or migrate page layouts.

## Architecture

```text
Workspace / Page
      ↓
Components / Patterns
      ↓
ui.design_system.theme
      ↓
ui.design_system.tokens   ← only visual-value authority
```

`tokens.py` is the only module allowed to own literal visual token values. `theme.py` is a read-oriented facade over those same dictionaries; it does not copy or redefine them.

## Semantic-first token model

New UI should use semantic names rather than implementation/palette names.

### Color

Preferred examples:

- `surface_app`
- `surface_page`
- `surface_card`
- `text_primary`
- `text_secondary`
- `text_muted`
- `border_default`
- `border_subtle`
- `action_primary`
- `action_primary_hover`
- `action_accent`
- `state_success`
- `state_warning`
- `state_danger`
- `state_info`

The AnTech brand accent is available as `action_accent`; it is intentionally not applied across existing screens in this task.

### Typography

Canonical font family:

`Segoe UI, Roboto, Arial, sans-serif`

The existing type-size keys remain supported (`page_title`, `section_title`, `body`, `caption`, etc.) and a shared `FONT_WEIGHTS` scale is added.

### Spacing

| Token | px |
| --- | ---: |
| `xs` | 4 |
| `sm` | 8 |
| `md` | 12 |
| `lg` | 16 |
| `xl` | 24 |
| `xxl` | 32 |
| `xxxl` | 48 |

### Radius

`RADIUS` owns `none/sm/md/lg/xl/pill`. `circle` remains as a compatibility alias for the pill value.

### Elevation

`ELEVATION` describes Qt-friendly shadow intent (`blur_radius`, offsets, alpha). Actual `QGraphicsDropShadowEffect` wiring belongs to the component layer, not this task.

### State

`STATES` gives a consistent visual contract for:

- default
- hover
- pressed
- selected
- disabled
- success
- warning
- danger
- info

Badge colors are derived from the same canonical palette/state tokens.

## Legacy compatibility

`ui/styles.py` used to be a second token owner and disagreed with the design system on values such as success/warning colors.

It is now a **compatibility facade**:

- `COLORS` points to `design_system.tokens.COLORS`;
- `SPACING` points to `design_system.tokens.SPACING`;
- its historical QSS constants resolve through semantic tokens;
- it contains no literal hex colors.

Existing imports can therefore keep working while later UI-PROD migrations replace them deliberately.

Legacy keys such as `primary`, `success`, `background`, `surface`, `border`, `muted`, etc. remain available in `COLORS`, but they are aliases to the V2 semantic values.

## Rules for follow-up UI work

1. Do not introduce a new palette in a workspace/page/component.
2. Do not add raw hex colors outside the canonical token file.
3. Prefer semantic names over `gray_*` or brand primitives.
4. Do not copy token dictionaries into another module.
5. Add a token only when it represents reusable design intent, not a one-off screen tweak.
6. Components may translate tokens into QSS/QPalette/QGraphics effects.
7. Screen migration is handled by UI-PROD-02 and later tasks.

## Verification

```bash
cd CenterManager
python -m pytest tests/test_design_system_tokens.py
python -m pytest tests/test_ui_inventory_tool.py
```

The UI-PROD-01 tests verify:

- the semantic token contract;
- the theme facade references the canonical objects;
- `ui/styles.py` no longer owns hex values;
- legacy aliases resolve to V2 semantics;
- badge state colors come from the canonical palette.

## Acceptance criteria

- [x] Color has one canonical owner.
- [x] Typography has one canonical owner.
- [x] Spacing has one canonical owner.
- [x] Radius has one canonical owner.
- [x] Elevation has one canonical owner.
- [x] Interaction/status state has one canonical owner.
- [x] Semantic tokens exist for new production UI.
- [x] Legacy token names remain compatible for incremental migration.
- [x] `ui/styles.py` is no longer a competing palette/scale.
- [x] Design System V2 public API exposes tokens and `theme`.
- [x] Contract tests prevent accidental reintroduction of a second source.
- [x] No business logic, database, service, navigation, or page-layout behavior changes.

## Non-goals

- component redesign;
- icon system;
- screen/workspace migration;
- app-shell redesign;
- Home Dashboard V2;
- table/form/dialog production patterns.

Those are handled in UI-PROD-02 and later tasks.
