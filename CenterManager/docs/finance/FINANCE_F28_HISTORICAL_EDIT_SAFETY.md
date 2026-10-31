# F-28 — Historical Income edit safety

Baseline: `main_repos@6d4b6dbd` (PR #521 merged; its Windows CI #775 passed). This audit uses synthetic SQLite records only. It does not assert that production contains a mismatched Income.

## Root cause and boundary trace

| Boundary | Before / evidence | After / guard |
|---|---|---|
| UI entry | `income_list_page.py:_show_edit_dialog` requires WRITE mode, `finance.income.update` and open selected period before constructing the modal editor. | Unchanged. Read-only detail remains available separately. |
| Load | `income_form_dialog.py:_load_classes` used `ClassService.list_classes()` (active list); `_load_income` only selected `class_id` when `findData` succeeded. For an archived Class, the first unrelated active class stayed selected. Synthetic test: persisted `class_id=1`, displayed `class_id=2` before fix. | `_load_income` uses `IncomeService.get_income`'s joined Student/Class/Enrollment references (`income_repository.py:get_by_id`) to append only the exact historical row when absent from operational options. Identity label shows persisted IDs. Missing rows show `UNRESOLVED` and disable Save. |
| Enrollment | `_reload_enrollments` initially selected the sole candidate, or left the selector on a placeholder with multiple contracts. A persisted reconciled-away/missing link could be invisible. | Rebuild selects the exact persisted Enrollment ID; a null legacy attribution remains explicitly null. A missing linked row blocks Save. Existing authorized `IncomeService.reconcile_tuition_enrollment` remains the separate attribution path. |
| Mutation | `income_form_dialog.py:_save` sent amount, wallet, date, period metadata, receiver and note on every Save. A no-change Save could normalize `payment_period=''` to `NULL` and create an UPDATE audit. It never sent Student/Class/Enrollment IDs, so the source record's three links were not silently replaced by the UI error. | The form checks its displayed identity against the loaded IDs and sends only changed nonidentity fields. No-change Save does not invoke `update_income`. The service still enforces `finance.income.update`, ACTIVE/nondeleted state, old and new period mutability and same-transaction audit (`income_service.py:update_income`, `_ensure_income_period_mutable`, `_record_audit`). |

The displayed class substitution was a **UI correctness risk**, not proof of historical database corruption. No backfill or reassignment is performed. Tuition after withdrawal/archive remains valid when linked to its exact old Enrollment; payment date determines ledger period, not teaching dates.

## Evidence and performance

- `tests/test_finance_f28_historical_income_edit.py` first reproduced the incorrect archived-class selection, then covers active and archived identities, missing references, null legacy attribution, multiple contracts, no-change and note edits, audit, VOIDED/deleted Income, confirmed period, unauthorized caller and option refresh while editing.
- With 250 unrelated archived Classes in one local synthetic SQLite run, edit load took 19.2 ms and 9 SQL statements. The Class combobox contains one active Class and only the persisted archived Class; the test asserts fewer than 30 SQL statements and no INSERT/UPDATE on load. This is local evidence, not an EXE latency target. The fix adds no historical Class catalog scan or per-row ORM lookup. Creation still uses operational Student/Class options and the bounded tuition search picker.
- No migration, production database access, ledger rewrite or new collaboration WRITE lease. A concurrent database mutation after form load is still checked by the service on Save; its existing period and status guards remain authoritative.

## Risk, rollback and UAT

Risk: malformed historical references may now block edits until an authorized reviewer resolves the source evidence; this is deliberate fail-closed behavior. A legacy Tuition row with a persisted null Enrollment can still receive a note edit without automatic attribution. Income period reclassification under retroactive configuration is the separate open F-21 policy risk and is not changed here.

Rollback: revert the UI/test/document commit; no schema or data rollback is required. Reverting restores the incorrect display risk, so do not use it to interpret historical IDs.

On an isolated Windows EXE with synthetic data: open Income with active and archived Class, withdrawn Enrollment and archived Student; verify exact IDs before and after a note edit and restart. Check missing references show `UNRESOLVED` and Save is disabled, a null legacy Enrollment stays null, and multiple contracts select the original ID. Verify VOIDED/deleted, viewer-only, closed period, parent list refresh while the modal editor is open, and authorized old-debt collection after archive/withdrawal. Confirm a no-change Save creates no audit UPDATE. Do not run this rehearsal against production data.
