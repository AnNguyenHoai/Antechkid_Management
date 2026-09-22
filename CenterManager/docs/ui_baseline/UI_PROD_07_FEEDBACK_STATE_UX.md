# UI-PROD-07 — Feedback & State UX

**Baseline:** `main_repos@d4bff46f975eb5f5a6774358930153052d4d1e8a`  
**Scope owner:** application feedback/state behavior only. Workspace migration remains in UI-PROD-08.

## Goal

Give CenterManager one consistent feedback language without moving permission,
validation, or business rules into the UI layer.

The product contract is:

- Save → `Saving…` → `Saved ✓`.
- Delete → consequential confirmation → deleted → optional `Undo` feedback.
- Load → `LoadingState` spinner or skeleton rows.
- Search with no results → `EmptySearchState`.
- Missing permission → `PermissionState`.
- System/runtime failure → readable recovery message; raw exception text is never
  rendered by default.
- Background sync → passive shell status, not an interrupting toast/dialog.
- Read-only / locked editing → reuse `EditStateBanner` from UI-PROD-06.
- `QMessageBox` is not the default feedback mechanism. Confirmation is reserved
  for consequential actions through the Design System dialog contract.

## Architecture

### 1. Application feedback

`FeedbackController` is a signal-based presentation controller. It has no service
or domain dependencies and therefore does not decide whether an operation is
valid or permitted.

Semantic feedback uses four tones:

| Tone | Default behavior | Typical use |
| --- | --- | --- |
| `info` | transient, 4.5 s | neutral acknowledgement |
| `success` | transient, 3.5 s | save/update completed |
| `warning` | persistent | recoverable condition needing attention |
| `danger` | persistent | operation/system error |

`FeedbackHost` is owned once by `ApplicationTopBar`, making application feedback
available through the shell instead of workspace-specific popup implementations.

### 2. Guarded operation state

`begin_operation()` establishes one active operation token and returns `False`
when another operation is already active. `finish_operation()` only clears the
matching token. This gives migrated call sites a small guard against accidental
double-submit.

Save flows should prefer:

```python
if top_bar.feedback_controller.begin_save("student-save"):
    try:
        service.save(...)
    except Exception as exc:
        log_exception(exc)
        top_bar.feedback_controller.save_failed("student-save")
    else:
        top_bar.feedback_controller.save_succeeded("student-save")
```

The service still owns validation and persistence. The UI only projects state.

### 3. Delete and Undo

Use `ConfirmationDialog(..., dangerous=True)` before a consequential delete.
For dangerous confirmation the destructive button is deliberately **not** the
Enter-key default; Cancel is the safe keyboard default.

After a successful delete:

```python
top_bar.feedback_controller.deleted(
    message="Student deleted",
    undo_action_id="student:42:restore",
    key="student:42:delete",
)
```

The host emits the action id when `Undo` is chosen. The owning workspace maps
that id to its restore/service action during UI-PROD-08 migration.

### 4. Content states

Page-level content states remain separate from application feedback:

- `LoadingState(message=..., skeleton_rows=0)` for indeterminate loading.
- `LoadingState(skeleton_rows=N)` / `Skeleton` when page structure is known.
- `EmptySearchState` for a search/filter result of zero.
- `PermissionState` when content/action is unavailable to the current role.
- `ErrorState` for recoverable page-load failures.

This avoids using a toast for a state that replaces the page content.

### 5. Read-only and disabled state

UI-PROD-06 remains the owner of form/detail edit hierarchy and permissions.
UI-PROD-07 reuses `EditStateBanner` (`readonly`, `editing`, `locked`) and does
not invent another permission or edit-state policy.

### 6. User-readable errors

`FeedbackController.system_error()` accepts the technical exception so the call
site can keep a consistent shape, but does not render `str(error)` by default.
Known domain failures may supply a safe translated `message`; logging/telemetry
stays with the owning flow.

### 7. Passive synchronization

`ApplicationTopBar.sync_label` remains the passive place for background sync.
Changing sync status does not publish feedback or open a dialog. Interruptive
feedback is reserved for a sync failure that actually requires user action.

## Compatibility

- Existing `ApplicationTopBar` transaction aliases are retained:
  `mode_label`, `waiting_indicator`, `tx_state_label`, `start_edit_btn`,
  `finish_edit_btn`, and `cancel_btn`.
- Existing `StateView`, `EmptyState`, `LoadingState`, `Skeleton`, `ErrorState`,
  form/detail, validation, and edit-state components are reused.
- No service/domain API is changed.
- No workspace is migrated in this task; Student → Class → Teacher → Finance →
  Employee → Admin migration belongs to UI-PROD-08.

## Regression guards

`tests/test_feedback_state_ux_v2.py` covers:

- feedback request validation;
- semantic tone and timeout policy;
- duplicate-operation guard;
- Save → Saving → Saved behavior;
- Delete + Undo feedback contract;
- raw exception text not leaking into system feedback;
- shell ownership of the shared feedback host;
- safe destructive confirmation defaults and no `QMessageBox` dependency in the
  new feedback primitive;
- search, permission, loading/skeleton, read-only/locked state coverage;
- passive background sync.

## Definition of Done

UI-PROD-07 is complete when new/migrated workspace flows have one canonical
feedback API, page states use the Design System state primitives, consequential
actions use the confirmation contract, read-only/disabled semantics remain
consistent with UI-PROD-06, and ordinary success/error feedback no longer needs
workspace-specific `QMessageBox` code.
