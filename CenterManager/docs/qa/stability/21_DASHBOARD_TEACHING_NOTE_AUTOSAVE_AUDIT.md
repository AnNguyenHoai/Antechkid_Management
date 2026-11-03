# UI-TEACH-01 / FIN-DASH-01: Dashboard and teaching history audit

**Date:** 2026-11-03. **Base:** main_repos `4470c4ae1893591e7d7e11a261149d0495588741`.
**Type:** targeted read-model/presentation and teaching-note UX change; **no DB schema migrations, Git MAIN publication changes or bypass of WRITE authority**.
**Evidence:** two user screenshots: Finance Dashboard selected 01/10/2026–31/10/2026, Teaching History (read-only) Session #10 on 03/11/2026.

## A. Finance Dashboard: observed vs proven

Screenshot:
- Selected October Income: **35,668,794 VND**.
- Bank In 24,968,794; Cash In 10,700,000; the numbers **reconcile exactly** to Income KPI.
- Expense Selected Period: 0; Cash Out: 0; Bank Out: 0; Net 35,668,794.
- Tuition Outstanding 525,000; Students With Debt 2; these were sourced from **all-course open Enrollment receivables** and must not be interpreted as October-only debt.
- Horizontal chart's Y ticks showed visually clipped numerical labels, e.g. truncated pieces of large VND values. That clipping is a **confirmed presentation bug**.

Code-level reason for reported Expense 0: `FinanceDashboardService.get_expense_by_payment_method` calls `ExpenseService.aggregate_by_payment_method`; `ExpenseRepository.aggregate_realized_amounts_by_payment_method` includes active rows whose dates fall in the selected range and status in `('Completed', 'Paid')`, excluding `Pending` by **accounting policy**. Zero realized expense may be correct even if planned/pending expense records exist. The screenshot alone cannot tell whether expense rows in the actual SQLCipher database were wrongly classified or never entered. Do not artificially change an accounting value without ledger reconciliation.

### Implemented fixes
- Rename paid expense KPI / cash-flow KPI to state the calculation scope explicitly; rename tuition debt/student count to '**all courses**', independent of period.
- Add visible explanation: current-period receipts and **Paid/Completed** expenses determine net, while tuition receivables are calculated across Enrollment wallets.
- Bar charts reserve readable axis space; Y ticks and value labels use compact K/M/B display, while hover tooltip retains the exact original full VND amount. Full precision data passed into calculations remains unchanged.
- No changes to Income/Expense aggregation, accounting-period binding, WalletService, Settlement or student debt ledger.

### Required financial evidence before asserting Expense is wrong
Read-only SQLCipher-clone query grouped by Expense.status and payment_date for October 2026, excluding deleted records. Independently compare pending vs Completed/Paid Expense amounts with Finance > Expense filter. Verify dates, payment methods, closed FinancePeriods, and the selected date. If Completed/Paid records exist in that period but Dashboard still shows zero, classify as a **proven aggregation bug** and fix under a separate financial-integrity PR with exact-row reconciliation. Never alter historical expense status to make a KPI nonzero.

## B. Teaching Note UX / redundancy

Screenshot is **Teaching History — Read Only**. The controls are intentionally disabled; **autosave must not run** in that window.

Observed source:
- `SessionDetailDialog` renders the session-level status `COMPLETED`.
- `SessionNoteWidget` additionally showed an editable `Teaching Progress` with `NOT_STARTED / IN_PROGRESS / COMPLETED / EXCEEDED_PLAN`; this duplicates much of the Session state.
- Save button was manual; users could edit a note but forget to persist changes.

### Implemented behavior
- Keep persisted `SessionNote.teaching_progress` column for historical compatibility, but remove the redundant visible field. New notes use `COMPLETED` only after `SessionNoteService` verifies the actual session is COMPLETED. Updates **omit** `teaching_progress`, preserving old `EXCEEDED_PLAN` and other historical values exactly.
- For editable Teaching Notes, debounce edits for 1.2 seconds on Class Atmosphere, Lesson Content and Homework; automatically call the existing service (no direct SQL from UI). This is **a local DB save during an authorized WRITE session, not a Git MAIN publication**; normal Finish Editing still controls authoritative publishing.
- Explicit Save now remains as recovery option. Auto-save has status: unsaved/saving/saved/failed.
- On service validation error, lost WRITE authority, or local persistence failure, **keep the exact draft in memory**, visibly mark not saved, and do not declare success.
- Before closing/rejecting the parent dialog or refreshing/switching session, flush pending edits. If flushing fails, keep the current dialog open/draft intact. Explicit Discard requires confirmation.
- On archived Teaching History, disabled composite note widget must never write. Existing SessionNote service/database WRITE authority gate remains unchanged. No automatic WRITE grant or draft publication.
- Do not refresh the note from storage immediately after a successful save: keep the service-confirmed record to avoid wiping a newer draft.
- Student Highlights already use immediate add/remove actions and are **not included** in note autosave (no unnecessary data writes).

### Known limitations / UAT
1. An OS kill during the 1.2-second debounce can still lose the pending in-memory edit; this is an interactive local autosave, not a durable crash journal for keystrokes. Do not claim crash-proof text storage.
2. App READ mode must not permit a persistent note edit. The backend mutation gate rejects unauthorized writes; the UI keeps the draft instead of hiding the failure. Verify with installed EXE.
3. The completed-session-only rule for creating new notes remains unchanged. This change does not design draft notes for SCHEDULED/IN_PROGRESS lessons.
4. Windows screenshot UAT: READ history (no enabled inputs, zero writes), editable completed session (auto-save after pause), failed WRITE mid-edit (preserved draft / close blocked), rapid switching, empty-string clear of previously filled Homework and Lesson Content, old EXCEEDED_PLAN preserved.
5. UAT on cloned SQLCipher & saved expense ledger is still required before releasing to production; exact-head Windows CI first.

## Test coverage
`test_qa_teaching_note_autosave_dashboard_chart.py` checks create/update with implicit progress, no WRITE in disabled history, failed autosave with retry, clearing optional text, compact axis ticks/tooltips and October screenshot cash/inflow arithmetic. Existing financial ledger tests remain untouched.


## Founder revision — replace autosave with Save & Close (2026-11-03)

The founder **rejected automatic timed writes** as unsafe. The final intended behavior in PR #553 supersedes the 1.2-second autosave proposal above:

- **No QTimer, no debounce and no write on field change or time passage.** A dirty form remains an in-memory draft.
- No separate Save button in Teaching Note. The parent dialog's **Close** footer changes to **Save & Close** only when the editable note has changes. It invokes the existing `SessionNoteService` exactly once and closes only after successful persistence.
- Window-X and Esc follow the same save gate, not a silent discard. If save is denied or fails, retain the dialog, preserve the full draft, warn the user, and permit retry after valid WRITE authority resumes.
- On READ-only historical session, widgets are disabled, no dirty changes are accepted, and Close simply closes without a DB write. The backend mutation authority guard remains mandatory.
- A refresh or session switch does not trigger an automatic persistence: if the note is dirty, it is refused with a visible Save & Close instruction. Explicit Cancel in the note is the **only** user-acknowledged unsaved draft discard path.
- The hidden legacy `teaching_progress` field continues to exist in the schema, with new completed-session notes storing COMPLETED and updates preserving historical progress.
- Changed Qt tests assert **no service calls during typing, field changes or event processing**, exactly one call on Close-save, failure preservation, inactive/READ behavior, and historical schema compatibility.

The earlier autosave section describes superseded implementation only. **No timed autosave behavior should ship.** Windows CI and EXE runtime UAT are still required before merge.
