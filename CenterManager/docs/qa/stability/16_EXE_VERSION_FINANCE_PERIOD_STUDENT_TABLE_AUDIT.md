# CenterManager — EXE Compatibility, Tuition Scope and Student Table Audit

**Date:** 2026-11-03  
**Audit base:** `main_repos`, commit `07b11f52a5584ac943b91015b144c9c6e215a540`.  
**Scope:** source inspection, narrow UI corrections, synthetic regression tests. NOT a production database inspection or real Windows EXE visual UAT.  
**Constraints:** Git MAIN is authoritative; no hosted coordinator/server; do not change financial ledger, legacy DB snapshots, credentials or active remote settings as part of UI fixes.

## A. EXE version / WRITE compatibility — P0 design gate

### Confirmed source observations

1. `core/version.py::get_application_version` reads immutable release identity from `CenterManager/VERSION` (source) or packaged `RELEASE_MANIFEST.json` (frozen). This is **SemVer string**, not database generation.
2. `platform/version/version_manager.py` publishes `runtime_version` integers, and `metadata/version.json` stores platform/pending versions. This is a **runtime publication counter** rather than a minimum-compatible EXE release. Do not confuse these.
3. Repository manifests contain `minimum_app_version` (existing default `0.1.0` in VersionManager's template), but current `services/write_transaction.py::start_editing` starts lock acquisition after recovery checks without evaluating app minimum; `platform/collaboration/collaboration_manager.py::request_write` has no app-version check at this entry point.
4. `platform/sync/startup_sync.py` already requires fresh remote MAIN verification before normal startup and records that MAIN authoritative. No proven end-to-end enforcement for older packaged binaries has been established from these inspected paths.

### Critical threat-model distinction

**A new client-side version check cannot constrain an already-deployed legacy EXE that ignores the check and retains credentials able to push authoritative Git MAIN.** Mark this as P0 residual risk. It is invalid to claim legacy DB overwrite is prevented until Git-side enforcement denies obsolete credentials/writers (e.g. a GitHub-protected publication identity / narrowly scoped GitHub Actions workflow / credential rotation and non-bypassable branch rules). This can be built without hosting a separate server, but is a separate release/permission decision.

### Recommended narrowly-scoped compatibility contract

- Admin publishes an immutable release `app_version` and a monotonic **minimum_writer_version** to Git as a release-operation with remote OID CAS, not as a side effect of each user's first startup. Retain optional `minimum_reader_version` for genuinely incompatible DB-schema upgrades. For absent/malformed/unverifiable remote policy: block WRITE (and fail normal startup if the authoritative DB cannot be verified). Do not silently treat missing policy as unrestricted legacy mode.
- A new EXE may **propose** a version bump on its first launch, but must not unilaterally publish a new minimum that instantly demotes other operators. Promotion requires authorized release gate and audit. Independently bump the `VERSION`/packaged `RELEASE_MANIFEST.json` with every distributed release, and validate the packaged identity.
- Use semantic version comparison (including release-candidate precedence); never string lexical ordering. Treat downgrade/nonmatching app identity as incompatible.
- Validate the current **freshly fetched** remote policy at startup, immediately before `request_write` (including waiting/grant handoff) and before Git MAIN publication; if policy observation fails mid-session, suspend edits/publish, retain durable journal, release lock only through fenced handoff. A read-only user can still see accepted MAIN if encrypted/schema compatible.
- The UI should show current version, required version and an actionable update warning, disable Start Editing and mutation actions. Read mode must never secretly run migrations, reports or background SQL writes.
- Version policy changing while another user is editing needs an explicit drain/writer cutover rule. Never set a new minimum during another user's accepted WRITE session without handling it under fencing.

### Acceptance tests before any version protection claim

V01 older EXE read-only, denied initial/queued WRITE; V02 missing/bad remote version policy denied WRITE; V03 current EXE accepted; V04 semver RC/prerelease correct; V05 remote change while WRITE waiting, while editing and just before publish; V06 Git offline or stale fetch; V07 local version file tampered; V08 old EXE with surviving PAT attempts direct push MAIN (must be **rejected Git-side**, or document protection not achieved); V09 recovery WRITE journal preserved on downgrade; V10 concurrent first-launch version races produce no lost update.

**Decision:** design-only. Do not implement a partial app-side gate as if it provides legacy Git publication fencing.

## B. Course-based tuition versus FinancePeriod — P0/P1 semantic audit

### Proven code behavior

- Tuition accrual is fundamentally tied to **Enrollment**: `services/tuition_accrual_service.py::calculate_from_records` counts billable teaching sessions before `as_of_date`, applies unit fee and proportional discount; `services/outstanding_service.py::_calculate_from_enrollment` joins this accumulated obligation to tuition payments summed for the same enrollment up to the cutoff. This remains a lifetime-to-date enrollment balance, not a monthly contract.
- `OutstandingService` exposes two distinct views: `VIEW_OPEN_RECEIVABLES` (unrestricted by FinancePeriod) and `VIEW_PERIOD_ACTIVITY` (filters enrollments overlapping the selected FinancePeriod), but **the latter still computes cumulative earned and cumulative paid since enrollment**, rather than isolating incrementally earned/paid within that reporting period. The label “Phát sinh trong kỳ” is therefore potentially materially misleading.
- `ui/finance_workspace/outstanding_list_page.py` already defaults its view selector to “Công nợ còn mở (tất cả kỳ)” before “Phát sinh trong kỳ”; preserving this distinction is preferable to removing FinancePeriod.
- `services/outstanding_service.py::get_student_summary` calls `get_outstanding_page` with the **default period-scoped view**, so a student financial overview can omit older enrollments not overlapping the reporting period while showing lifetime paid/accrued amounts of included enrollments.
- `ui/student_workspace/student_financial_widget.py::set_student` resolves an accounting period, calls `_load_outstanding_summary(period_start, ...)` and separately `_load_incomes` filtered by **finance_period_start** and payment dates. Thus the total paid in enrollment summary and the visible payment-history rows can refer to **different scopes** even though displayed together.
- `services/wallet_service.py` aggregates cash/bank Income and Expense by period for accounting settlement. These cash/bank wallets must not be conflated with an enrollment's tuition/prepayment credit: they answer different questions and **should remain period-based**.
- Additional source defect: `OutstandingService.get_all_outstanding` forwards `hide_settled_inactive=hide_settled_inactive` although the method signature does not define this variable. Any executed call through that path can raise `NameError`. Resolve separately with a regression test.

### Business terms that must not be mixed

1. **Contract total** = planned billable sessions × contract rate − contracted discount / agreed adjustments.
2. **Accrued to date** = billable sessions actually due as of cutoff × fee − applicable discount.
3. **Total paid to date** = valid active tuition Income tied to the same Enrollment as of cutoff, net of reversed/refunded items per ledger policy.
4. **Currently collectible debt** = max(0, accrued-to-date − paid-to-date) (unless the contract has different due-date policy).
5. **Remaining contract commitment** = contract total − accrued-to-date, not yet necessarily overdue.
6. **Accounting-period movements** = receipts/realized Income, expenses and recognized accrual changes strictly inside period, not outstanding balance rebadged as monthly activity.

Example synthetic enrollment: 24 planned sessions at 100k/session, 8 billable sessions accrued, 500k paid. Contract commitment 2.4m, earned 800k, currently collectible 300k, future unearned 1.6m. A 1-month accounting window does not split the contract or create a new Enrollment.

### Recommended solution — preserve ledger, separate projections

- Keep Enrollment as tuition obligation identity and the exact per-session billing policy. Do not migrate historical transactions or reset wallet balances just to change visual grouping.
- Make **“Nợ theo Enrollment/toàn khóa đến ngày X”** the primary tuition collection view and Student Financial summary; calculate globally by Enrollment ID, independent of FinancePeriod. Distinguish “đã phát sinh”, “đã thu”, “còn phải thu” and “chưa phát sinh của khóa”.
- Keep FinancePeriod for realized cash/bank reporting, WalletService, Settlement, Income/Expense bookkeeping. For period movement view, compute **opening balance + period accrual − period payments ± adjustments = closing balance**; implement this reconciliation explicitly rather than filtering Enrollment start/end alone.
- If period does not exist, do not make course collection/inquiry disappear; only accounting-period report/settlement needs a configured FinancePeriod.
- Preserve canceled, withdrawn, archived and repeated Enrollments by exact ID; avoid joining only student/class; handle tuition credits/refunds and mixed unconfigured policies transparently.
- UI should label ledger scope and cutoff, not mix period-filtered payment history with lifetime summary without explanation. Provide a separate “Tất cả giao dịch của khóa” history when studying collection.
- Regression cases: payment crossing months, upfront prepay, 24-session course spanning 4 months, class archive with debt, enrollment withdrawn and rejoined, old periods closed, no FinancePeriod configuration, refunds/voided Income, two simultaneous enrollments, as-of cutoff, unresolved pricing, repeated enrollment in the same class and reconciliation of accounting-period cash movements.

**Decision:** do not alter money calculations or database schema until the required collection/due-date rule is confirmed; start with read-model and UI clarity tests. No production financial writes performed in this PR.

## C. Student / debt / attendance tables — source-based UI findings and fix

- `ui/shared/data_table.py` uses `QTableWidget`, interactive headers and right-side tooltip for full cell values. Qt scrollbars are available, but former widget-specific `ResizeMode.Stretch` in both `ui/student_workspace/student_financial_widget.py` tables forced columns to fill narrow viewports (risk: excessively small headers/cells, elided text).
- `ui/finance_workspace/outstanding_list_page.py` has seven columns. `ui/class_workspace/monthly_attendance_exceptions_page.py` has nine. At narrow widths or high Windows display scaling, columns require explicit horizontal overflow. `ui/student_workspace/student_attendance_widget.py` uses the shared DataTable with four columns; `ui/student_workspace/student_list_page.py` uses five columns. These two do not exhibit the same forced Stretch override in the inspected source.
- Student Detail already wraps Enrollment and Finance tabs in `QScrollArea` (`ui/student_workspace/student_detail_page.py`), so vertical scrolling exists at tab level. The specific inner table horizontal scroll is independent.
- A screenshot-based verdict that every table renders without clipping **cannot** be claimed from source inspection alone. Windows/DPI visual UAT is still required.

### Implemented in this audit PR

- Student finance detail and history: remove `Stretch`, retain `Interactive` widths, disable stretch-last-section; explicit horizontal/vertical as-needed scrollbars; give each column a usable base width.
- Outstanding list (7 columns) and monthly attendance exceptions (9 columns): explicit scrollbars and minimum-friendly set widths, disable stretch-last.
- New synthetic Qt regression tests place grids at ~465px and verify horizontal scrolling occurs. No data calculations or table sorting/selection code changed.

### UI UAT matrix

Test window widths 1920 / 1366 / 1024 / 800 / 640 logical pixels and Windows scaling 100 / 125 / 150%; long student and class names; large VND amounts; archived class; 100+ absent/missing records; keyboard horizontal navigation; touchpad trackpad wheel/horizontal shift; both scroll axes; pagination and row selection after horizontal scroll; footer and toolbar are still accessible. Ensure the horizontal scrollbar appears **within the grid**, not by compressing all columns or clipping content without affordance.

## Recommended priority / execution order

1. **P0 release safety:** decide whether Git-side legacy publisher blocking is required, and define SemVer promotion policy; do not claim old EXEs are fenced by an app-only version check.
2. **P0 finance display truth:** separate Enrollment lifetime debt from period movements; add reconciliation tests before changing calculation behavior.
3. **P1 UI visibility:** merge only after new Qt tests and Windows scaling screenshots PASS. This PR implements narrow UI fixes; actual Windows visual UAT is still pending.
4. **P1 separate defect:** fix undefined `hide_settled_inactive` in `get_all_outstanding` with focused regression tests.


## Founder decision — scope update (2026-11-03)

The EXE-version / legacy-publisher fencing work is explicitly **DEFERRED** by the founder. No release-version authority, client-version gate or Git credential enforcement is implemented in this PR. Its prior architecture audit remains a reference only.

### Course-based tuition implementation in this PR

- Introduced explicit `OutstandingService.VIEW_COURSE_BALANCES`: returns balances for all Enrollment identities regardless of FinancePeriod, including paid/prepaid/unconfigured cases. It is **not** the existing `VIEW_OPEN_RECEIVABLES` (which deliberately shows only still-owed balances).
- Student Financial page uses that view as the primary course-to-date summary, with an as-of cutoff. It does not depend on the existence of FinancePeriod configuration.
- Student Financial tuition payment history is limited to active `Tuition` Income across all FinancePeriods through the same as-of date, not mixed Income types or only the current period.
- The Finance Outstanding page's old 'Phát sinh trong kỳ' label was not semantically correct: the underlying rows are cumulative Enrollment balances for contracts overlapping the period. Rename to `Enrollment giao kỳ (số dư lũy kế)` and label totals as cumulative until proper opening/activity/closing movement projection is independently implemented.
- Fix `get_all_outstanding` forwarding of undefined `hide_settled_inactive` variable, accepting it as an explicit optional argument and forwarding the selected view.
- **No mutation of Income, Enrollment, TuitionAccrual, FinancePeriod, Wallet, Settlement or database schema.** Existing financial period settlement remains the accounting record.

### Remaining design limitation

The true period movement formula (opening balance + newly accrued sessions − newly received attributed Tuition payments ± adjustments = closing balance) is **not** yet implemented. The period-filtered view is accurately described as a cumulative balance, not mislabeled as a period movement. Historical refunds, re-enrollments, unconfigured contracts and actual database values still require financial UAT/reconciliation.

### Added tests

`test_qa_course_tuition_scope.py` asserts the all-Enrollment read view bypasses FinancePeriod resolution, keeps exact Enrollment identities, forwards the old list adapter without NameError and presents all-time active Tuition history with the selected as-of cutoff. `test_qa_ui_narrow_table_scroll.py` checks visible horizontal scrolling on narrow grids.

Merge gate: Windows CI on exact PR head plus financial comparison against a cloned SQLCipher DB and 100/125/150% DPI visual checks. No live DB or Git MAIN changes.


### Per-Enrollment credit isolation — additional finding and implementation

A separate cross-course netting issue was confirmed: `StudentOutstandingSummary.total_outstanding = total_expected - total_paid` is a **signed reconciliation** and may offset debt from Enrollment A with prepaid credit from Enrollment B. Under the center's per-course credit policy this is not a valid collectible-debt number. The underlying `OutstandingDTO` already exposes per-Enrollment `debt_amount` and `prepaid_amount` and the Finance Outstanding stats already sum these **separately**.

This PR changes `StudentOutstandingSummary.debt_amount` and `.prepaid_amount` to aggregate exact Enrollment details independently (only for configured tuition), and changes the Student Financial headline to show **receivable debt without credit offset**. The independent prepaid amount is shown as a separate status when nonzero. `total_outstanding` remains a signed historical/reconciliation amount for backwards compatibility; it must not be used as collectible debt. Existing ledgers/Income/Enrollment records are untouched. Added regression for Enrollment 42 debt 300k plus Enrollment 43 prepaid 150k: collectible debt must be 300k and credit 150k, not net 150k.

This adjustment does **not** authorize cross-course transfers or credit reassignment. Such transfers would require an explicit audited business workflow outside this change.
