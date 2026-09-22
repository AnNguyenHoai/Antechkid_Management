# UI-PROD-03 — Application Shell V2

## Goal

Turn the current workspace chrome into one production shell with clear ownership of:

- global application state;
- workspace navigation;
- page context;
- user identity;
- collaboration / edit state.

UI-PROD-03 builds on Design System V2 and Component Foundation V2. It does not change business behaviour, permissions, navigation destinations, database/service contracts, or the write-transaction state machine.

Base revision:

`main_repos@7526b081e576c90cab0d8fda5ef85b931e446286`

## 1. Shell hierarchy

```text
MainWindow
├── ApplicationTopBar
│   ├── product identity
│   ├── runtime / sync status
│   ├── READ / WRITE / conflict state
│   ├── current edit owner
│   ├── Start / Finish / Cancel edit actions
│   └── current user / role
└── central_stack
    ├── Home
    └── Workspace
        ├── WorkspaceHeader
        │   ├── Breadcrumbs
        │   └── Page title
        └── body
            ├── WorkspaceNavigation
            └── content_stack
```

This separates global state from page context. Workspace headers no longer carry application-wide collaboration details, and the status bar is no longer used as a permanent technical control strip.

## 2. Application top bar

`ui/application_shell.py` introduces `ApplicationTopBar`.

It owns the visual projection of:

- product identity: AnTechKids / Center Manager;
- current authenticated user and role;
- runtime version;
- synchronization status;
- write mode;
- current active editor;
- transaction status text;
- edit lifecycle actions.

The existing transaction lifecycle remains in `MainWindow` / `WriteTransactionManager`.

The top bar only projects that state and emits:

- `start_edit_requested`;
- `finish_edit_requested`;
- `cancel_edit_requested`.

For migration safety, the existing MainWindow attributes remain available as aliases:

- `mode_label`;
- `user_label`;
- `version_label`;
- `sync_label`;
- `waiting_indicator`;
- `start_edit_btn`;
- `finish_edit_btn`;
- `cancel_btn`;
- `tx_state_label`.

This allows existing tests/event handlers to continue working while the visual owner moves from the status bar to the application shell.

## 3. Status bar responsibility

Before UI-PROD-03 the status bar permanently displayed technical controls such as runtime, mode, sync, lock ownership, and edit actions.

After UI-PROD-03:

- permanent shell state lives in `ApplicationTopBar`;
- `QStatusBar` is retained only for temporary feedback/messages;
- no permanent widget is added to the status bar.

## 4. Sidebar

`WorkspaceNavigation` remains the shared API used by Student, Teacher, Class, Finance, Employee and Admin workspaces.

V2 changes:

- text-first navigation;
- legacy emoji/icon input is accepted but not rendered in the label;
- semantic hover / selected / focus states;
- selected state uses the AnTech blue navigation language;
- small orange workspace eyebrow provides brand signature without flooding the UI with accent color;
- sidebar geometry comes from Design System tokens.

The existing navigation contract remains unchanged:

```python
page_selected = Signal(str)
set_active_page(page_id)
```

## 5. Page header and breadcrumbs

`WorkspaceHeader` now owns page-local context only.

It contains:

- Home breadcrumb action;
- workspace breadcrumb;
- active page breadcrumb;
- active page title.

Existing compatibility is preserved:

```python
back_home_clicked = Signal()
header.home_btn
header.context_label
header.set_context(workspace_name, page_label)
```

`context_label` remains available for legacy callers/tests but is hidden; production UI uses the breadcrumb + page-title presentation.

## 6. User / edit state semantics

ApplicationTopBar uses semantic badge tones instead of local raw colors.

| Situation | Mode | Editor state |
| --- | --- | --- |
| no editor | READ / neutral | No active editor |
| another user editing | READ / warning | `<user> is editing` |
| current user editing | WRITE / success | You are editing |
| publish conflict | CONFLICT / danger | Resolve before editing |
| finishing | FINISHING / warning | transaction detail |

The underlying write-lock and collaboration semantics are unchanged.

## 7. Token ownership

UI-PROD-03 extends `COMPONENT_METRICS` with shell geometry:

- `app_top_bar_height`;
- `workspace_sidebar_width`;
- `workspace_sidebar_header_height`;
- `page_header_height`;
- `nav_indicator_width`.

Shell modules contain no raw hexadecimal colors.

```text
Application Shell
       ↓
Component Foundation V2
       ↓
Theme / Tokens
```

## 8. Scope guard

UI-PROD-03 intentionally does not:

- redesign Home content;
- redesign workspace dashboard/list/detail content;
- change table UX;
- change forms;
- change permission rules;
- change collaboration/write state machine;
- change service/repository/database behaviour;
- replace domain navigation destinations.

Those are handled by later UI-PROD tasks.

## 9. Verification

```bash
cd CenterManager
python -m pytest tests/test_application_shell_v2.py
python -m pytest tests/test_component_foundation_v2.py
python -m pytest tests/test_design_system_tokens.py
python -m pytest tests/test_ui_inventory_tool.py
```

Full Windows pytest remains the merge gate.

## Acceptance criteria

- [x] Global top bar exists above application content.
- [x] Runtime, sync, user, role, mode and edit ownership are projected in the top bar.
- [x] Start / Finish / Cancel edit actions are in the top bar.
- [x] Status bar is notification-only.
- [x] Shared workspace sidebar is token-driven and text-first.
- [x] Shared workspace header includes breadcrumbs and page title.
- [x] Existing workspace navigation APIs remain compatible.
- [x] Existing MainWindow transaction attributes remain compatible.
- [x] Shell dimensions are token-owned.
- [x] Shell source contains no raw hex colors.
- [x] Automated shell contract tests are included.

## Next step

UI-PROD-04 can redesign the Home Dashboard on top of this shell without re-solving application navigation, identity, or collaboration state presentation.
