# UI-PROD-10 — Physical Windows UI UAT Checklist

## Setup
Run against the exact release candidate/source commit being accepted. Use disposable/demo data only. Record the exact source commit and build version in the evidence JSON. Keep screenshots in the same evidence directory; do not commit screenshots that contain real student information.

Before testing, record two expected release values from the release candidate being accepted:

- exact 40-character source commit SHA;
- exact application build version.

These values are supplied separately to the final verifier so an evidence file from another build cannot pass merely because its provenance fields are well-formed.

For each scenario: perform the observations, capture one representative PNG, mark the scenario `PASS` only when every item succeeds, and add notes for anything unusual.

## 1. shell-1366x768 — 100%
- Window opens fully on-screen and remains usable without clipped primary navigation.
- Application top bar, workspace header, sidebar and main content have clear hierarchy.
- Runtime/sync/user text does not push edit actions off-screen.
- Scrollbars appear only where content genuinely overflows.

## 2. shell-1920x1080 — 100%
- Content does not stretch into visually empty, oversized headers/toolbars.
- Cards/tables remain readable and aligned; spacing still feels intentional.
- Workspace title/breadcrumb hierarchy remains visually dominant over content metadata.

## 3. shell-scale-125 — >=125%
- Text is readable with no cropped labels or buttons.
- Header heights accommodate scaled font metrics.
- Focus borders, tooltips, menus and scrollbars remain visually usable.
- Long runtime/user/breadcrumb text ellipsizes instead of breaking the shell.

## 4. student-list-read
- Search/filter/sort/refresh remain usable in READ mode.
- Mutation actions are disabled/hidden according to the edit-state contract.
- DataTable density, row alignment and empty-search behavior are clear.

## 5. student-list-write
- Enter WRITE mode and confirm editing state is immediately visible.
- Mutation actions become available without changing navigation/layout unexpectedly.
- Finish/cancel edit actions remain reachable at 1366×768.

## 6. student-form-validation-save
- Trigger required-field validation and confirm errors are inline, readable and attached to the correct field.
- Correct the data and save; observe `Saving…` followed by the canonical saved feedback.
- No blocking legacy QMessageBox appears in the migrated Student form flow.

## 7. student-detail-tabs
- Open Student Detail and traverse Profile/Summary/Parents/Assessment/Timeline/Notes/Documents.
- Active tab, page title and student context remain obvious.
- Long values wrap/ellipsize without overlapping controls.

## 8. enrollment-confirmation-feedback
- Trigger a meaningful enrollment transition and confirm the production confirmation dialog is clear.
- Cancel once and verify no change occurs.
- Confirm once and verify completion/withdrawal feedback is readable and non-duplicated.

## 9. loading-empty-error-permission
- Observe at least one loading state, empty/no-results state, recoverable error state and permission/read-only state.
- Each state explains what happened and what the user can do next.
- Global feedback does not obscure page-local state or navigation.

## 10. window-restore-overflow-focus
- Resize/move the app, close normally, reopen and verify geometry restores on-screen.
- Simulate long user/runtime/breadcrumb text and verify ellipsis + tooltip behavior.
- Navigate core controls by keyboard and verify visible focus treatment.
- If monitor/layout changes, restored geometry must not strand the window off-screen.

## Final gate
1. All ten evidence records are `PASS` and point to unique PNG screenshots.
2. Run:

   ```powershell
   python scripts/verify_ui_uat.py <evidence.json> `
     --expected-source-commit <EXACT_40_CHAR_RELEASE_SHA> `
     --expected-build-version <EXACT_RELEASE_VERSION>
   ```

   and obtain `UI-PROD-10 UAT PASS`.
3. Confirm the verifier output source commit/build version are the exact release candidate being accepted.
4. Full pytest / visual regression CI is green for the same source commit.
5. Any production defect is fixed separately with regression coverage; do not simply move the visual baseline.
