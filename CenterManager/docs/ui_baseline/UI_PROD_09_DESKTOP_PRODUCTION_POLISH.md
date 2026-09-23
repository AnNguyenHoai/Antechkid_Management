# UI-PROD-09 — Desktop Production Polish

## Goal

Move the desktop shell from a functional V2 migration to a production-ready desktop experience without changing business behavior or workspace ownership.

## Scope

### Desktop window behavior

- Restore the previous usable window geometry through `QSettings`.
- Reject restored geometry that is no longer on an available screen after monitor changes.
- On first launch, size the window from the current available desktop and center it.
- Preserve `MainWindow` as the owner of minimum size and close/transaction behavior.

### Application shell overflow

- Add `ElidedLabel` for runtime, synchronization, transaction, user, role, and breadcrumb text.
- Preserve the full semantic `text()` value and expose it through tooltip/accessibility text while rendering an ellipsis when horizontal space is constrained.
- Keep all UI-PROD-03 compatibility aliases and the 60px idle top-bar contract.

### Desktop-native polish

Apply token-driven styling for native surfaces that previously looked inconsistent with Design System V2:

- context menus;
- tooltips;
- vertical and horizontal scrollbars;
- focus border fallback for legacy native form controls.

No competing palette is introduced; all colors, spacing, radius and typography values come from Design System V2 tokens.

### Workspace hierarchy

- Use the existing `page_title` typography token for visible workspace page titles.
- Replace fixed page-header height with a token-owned minimum height so desktop font metrics cannot clip the header.
- Preserve breadcrumbs, Home navigation and `set_context()` contracts.

## Architecture

`design_system/desktop.py` owns desktop presentation policy. `ApplicationTopBar` installs it on the owning `QMainWindow`, which avoids introducing desktop concerns into transaction, collaboration, synchronization, or workspace business logic.

Geometry persistence is handled by a small event-filter controller attached to the main window. It listens only to move/resize/window-state changes and does not intercept close events.

## Non-goals

- No business service, repository, database, permission, collaboration, or synchronization changes.
- No workspace-specific redesign.
- No dark-mode implementation.
- No new navigation behavior or keyboard command system.
- No removal of legacy compatibility aliases required by existing tests/integrations.

## Definition of done

- Desktop window opens at a sensible screen-aware size and can restore its previous geometry.
- Long top-bar metadata cannot force uncontrolled horizontal growth.
- Native menus/tooltips/scrollbars visually match Design System V2.
- Workspace page hierarchy is clearer and header height is font-safe.
- Existing UI-PROD-03/UI-PROD-07/UI-PROD-08 contracts remain intact.
- Regression coverage protects geometry, overflow, token ownership and header hierarchy.
