# UI-PROD-04 — Home Dashboard V2

## Goal

Turn Home from a large workspace launcher into a compact operational landing page on top of Application Shell V2.

Home must answer three questions quickly:

1. Which operational areas are available to the current user?
2. Which visible areas report healthy or attention-needed state?
3. How can the user enter the relevant workspace with minimal friction?

## Scope

UI-PROD-04 changes presentation only. It does not add business queries, permission rules, repositories, database models, or workspace navigation destinations.

The page consumes the existing `HomeDashboardService.get_workspace_summaries()` contract. Permission filtering therefore remains service-owned.

## Information hierarchy

```text
ApplicationTopBar
└── Home Dashboard V2
    ├── Compact page introduction
    │   └── Refresh action
    ├── Operational snapshot
    │   ├── Available workspaces
    │   ├── Healthy
    │   └── Needs attention
    ├── Attention summary (conditional)
    └── Workspaces
        └── compact workspace access cards
```

The previous large AnTech Kids hero and slogan are removed because product identity is already represented globally by Application Shell V2.

## Operational snapshot

The three snapshot values are derived only from the workspace summaries already returned by the service:

- **Available workspaces** — number of returned summaries.
- **Healthy** — summaries whose `health_status` is `good`.
- **Needs attention** — summaries whose `health_status` is `warning` or `critical`.

No domain metric is parsed from `summary_text`, and no synthetic revenue, attendance, session, or student figures are created in the UI.

## Workspace cards

`WorkspaceCard` remains API-compatible with the existing constructor and `clicked(str)` signal, but its V2 presentation is text-first:

- workspace name,
- semantic health badge,
- description,
- service-provided summary text,
- service-provided health details when present,
- compact quick action.

The legacy `icon` argument is retained for compatibility but is intentionally not rendered. This removes the previous mixed emoji icon language without changing `HomeDashboardService` in this task.

## States

Home Dashboard V2 uses Design System V2 states:

- normal dashboard content when summaries are available,
- `EmptyState` when no workspace summary is available,
- recoverable `ErrorState` when loading fails,
- retry/manual refresh through the existing service cache invalidation contract.

Errors are presented to the user rather than only being printed to the console.

## Layout

- root content is scrollable,
- horizontal scrolling is disabled,
- three compact snapshot tiles share one row,
- workspace cards use a three-column desktop grid,
- page content uses semantic spacing tokens,
- the layout remains usable at the application's 1000px minimum width and is optimized for 1366×768 and above.

## Design System ownership

Home V2 consumes:

- `Button`,
- `Badge`,
- `EmptyState`,
- `ErrorState`,
- semantic color, typography, spacing, radius and component tokens.

The Home V2 production sources contain no raw hex color literals and do not import the legacy `ui.styles` facade.

## Preserved contracts

The following contracts remain intact:

- `HomePage.workspace_selected = Signal(str)`
- `HomePage._populate_workspace_cards()`
- `HomePage._cards`
- `WorkspaceCard.clicked = Signal(str)`
- existing `WorkspaceCard` constructor arguments, including `icon`
- `HomeDashboardService.get_workspace_summaries()`
- service-owned permission filtering
- existing workspace IDs and destinations

## Verification

```bash
cd CenterManager
python -m pytest tests/test_home_dashboard_v2.py
python -m pytest tests/test_application_shell_v2.py
python -m pytest tests/test_component_foundation_v2.py
python -m pytest tests/test_design_system_tokens.py
```

The repository's full Windows pytest workflow remains the merge gate.

## Acceptance criteria

- Home reads as an operations dashboard rather than a marketing/launcher screen.
- Product branding is not duplicated below the global shell.
- Only service-returned workspaces are rendered.
- Workspace navigation signals remain unchanged.
- Health status is shown semantically and attention details remain visible.
- Empty and error states are explicit and recoverable.
- No new domain queries or permission logic are introduced in Home UI.
- No raw colors or emoji literals are introduced in Home V2 production sources.
- Content is scrollable and practical at production desktop sizes.

## Follow-up

UI-PROD-05 can build the shared data-heavy UX patterns (tables, filters, bulk actions, density and pagination) on top of the stabilized shell and Home landing experience.
