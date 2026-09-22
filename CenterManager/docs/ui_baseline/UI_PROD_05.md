# UI-PROD-05 — Data-heavy UX

## Goal

Standardize the high-density operational experience used by Student, Class,
Teacher, Finance and later workspaces without introducing a second table system.
UI-PROD-05 upgrades the existing shared `DataTable` and `SearchToolbar` in place,
adds a reusable bulk-action strip, and migrates Student List as the representative
production screen.

## Data-heavy interaction model

A data-heavy page should compose the following layers:

1. page/workspace shell from UI-PROD-03;
2. a shared search/filter row;
3. page actions using Design System V2 buttons/toolbars;
4. selection-aware bulk actions only when rows are selected;
5. a shared data table with explicit density, sort state and pagination;
6. inline empty/loading/error presentation for the table region.

Business rules, repositories and service filtering remain outside these UI
primitives.

## `DataTable` V2

`centermanager.ui.shared.DataTable` remains the canonical table component. Existing
public signals and pagination methods are preserved:

- `selection_changed(list)`;
- `sort_requested(str, bool)`;
- `row_double_clicked(int)`;
- `context_menu_requested(QPoint, int)`;
- `page_requested(page, page_size)`;
- `set_data(...)` for local pagination;
- `set_server_data(...)` for service/server pagination;
- `clear_selection()`.

UI-PROD-05 adds:

- `TableDensity.COMPACT` and `TableDensity.COMFORTABLE`;
- token-driven table/header/footer styling;
- explicit result ranges such as `1-20 of 87`;
- text-first Previous/Next pagination controls;
- semantic page-size `Select` control;
- visible sort indicator while keeping sorting ownership with the page/service;
- inline empty/loading/error states;
- `data_index_for_visible_row()` and `selected_data_indices()` so local pagination
  cannot accidentally address the wrong backing record.

The visible-row mapping deliberately does not change old signal semantics. Existing
consumers continue receiving page-local row indices; migrated consumers opt into the
safe mapping API.

## `SearchToolbar` V2

The existing `SearchToolbar` is upgraded rather than replaced.

Compatibility:

- `search_changed(str)` remains unchanged;
- `filter_changed(dict)` still emits the historical one-key delta;
- `text()`, `setText()` and `setPlaceholderText()` support incremental migration.

New contract:

- `filters_changed(dict)` emits the complete filter state;
- `filters()` returns that full state synchronously;
- `set_filter_value(key, value)` supports programmatic restoration;
- search, selects and clear action use Design System V2 `Input`, `Select` and
  `Button` components;
- no raw colors, emoji search symbols or page-owned control geometry.

New screens should prefer `filters_changed` when multiple filters combine into one
service query/DTO.

## `BulkActionBar`

`BulkActionBar` is the shared selection-aware action strip. It:

- stays hidden at zero selection;
- owns the selected-count presentation;
- accepts named semantic actions;
- keeps Clear selection as a stable trailing action;
- uses Design System V2 button variants, including danger for destructive actions;
- does not own permission or mutation logic.

Permission state remains page-owned. For example, Student List disables the delete
bulk action outside WRITE mode while export remains read-only.

## Representative migration — Student List

Student List now proves the complete data-heavy pattern:

- `Toolbar` + `SearchToolbar` for search and three common filters;
- existing advanced-filter dialog remains available through `filter_clicked`;
- all toolbar actions are text-first, with no emoji icon language;
- `BulkActionBar` owns multi-selection presentation;
- `DataTable` runs in compact density with 20 rows per page;
- loading/error/empty states are contained in the table region;
- the existing StudentFilter DTO/service pipeline is unchanged;
- WRITE/read-only rules and collaboration checks are unchanged.

### Pagination correctness hardening

Before this migration, Student List received page-local row indices from
`DataTable` and indexed directly into the full filtered student list. On page 2,
visible row 0 could therefore resolve to the first student from page 1 for
selection, double-click and context-menu actions.

The migrated page uses `data_index_for_visible_row()` for:

- multi-selection;
- double-click navigation;
- context-menu actions.

This fixes addressing without changing the legacy table signal contract.

## Token ownership

UI-PROD-05 adds geometry only to `COMPONENT_METRICS`:

- `data_table_header_height`;
- `data_table_row_height_compact`;
- `data_table_row_height_comfortable`;
- `data_table_footer_height`;
- `data_table_min_column_width`;
- `data_bulk_bar_height`;
- `data_filter_min_width`;
- `data_search_min_width`.

Colors, typography, radius and spacing continue to come from the existing Design
System V2 token families.

## Scope guard

Not changed in UI-PROD-05:

- repositories/database models;
- Student service/filter/import/export implementations;
- permission definitions;
- collaboration/write-lock semantics;
- application routing;
- other workspace business logic;
- global feedback architecture reserved for UI-PROD-07.

## Verification

Run from `CenterManager`:

```bash
python -m pytest tests/test_data_heavy_ux_v2.py
python -m pytest tests/test_component_foundation_v2.py
python -m pytest tests/test_design_system_tokens.py
python -m pytest
```

The Windows full pytest workflow remains the merge gate.

## Acceptance criteria

- one canonical shared table system, no parallel replacement;
- local and server pagination contracts remain available;
- compact and comfortable density are token-owned;
- search/filter state is composable and backward compatible;
- selection reveals standard bulk actions;
- empty/loading/error states stay inside the data region;
- Student List demonstrates the V2 pattern without service changes;
- row actions address the correct backing record on every local page;
- no raw colors, emoji literals or `ui.styles` imports in migrated V2 sources.

## Follow-up

UI-PROD-06 can now standardize Form & Detail UX on top of the same shell and
component foundation. Broader workspace adoption remains part of UI-PROD-08 so
UI-PROD-05 stays focused on the reusable data-heavy interaction model.
