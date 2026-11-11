# CENTERMANAGER — END-TO-END BUSINESS WORKFLOWS (READ FIRST)

**Document ID:** CM-WF | **Version:** 1.1 | **Updated:** 2026-11-11
**Verified pre-hardening baseline:** `main_coursefee` @ `1ea1f8a1be902d524825a24ea9fa9193c362830d`. Hardening changes tracked in phase PRs; always resolve current HEAD and packaged SHA at release.
**Paired authoritative index:** [CENTERMANAGER_REQUIREMENTS.md](CENTERMANAGER_REQUIREMENTS.md).

> **MANDATORY:** Before changing a feature, read **both documents**, locate its `WF-xx` flow and `CM-REQ` requirement IDs, follow the implementation links and tests, then record how normal, historical, permission and failure paths will behave. This describes the **course-based** CenterManager tool. The monthly-tuition product exists separately and is NOT this release.

## How to read this file

Every workflow records **actor/trigger → prerequisites → steps → accepted output → exceptions/invariants → code entry points**. Steps are business contracts at a stable level; actual UI wording, service signatures and schema constraints must be verified at the source HEAD before modifying them. `[VERIFY]` means the flow or edge case needs a real Windows/SQLCipher UAT rather than assumed proof. Terms:
- **Source branch** = program code (for this edition `main_coursefee`).
- **Git DB MAIN** = private authoritative data repository's configured branch (currently `main`).
- **Runtime DB** = currently active local SQLCipher database materialized from accepted Git MAIN.
- **READ** = browse authorized information, no business mutation.
- **WRITE/Edit session** = exclusive remotely verified editing authority; still requires domain capabilities.
- **Recovery evidence** = historical local changes and diagnostic files for human review; **never a second automatic source of truth**.
- **FinancePeriod** = accounting/Settlement range, not course/session pricing period.
- **Enrollment** = one student's particular tuition and teaching contract in a class, with its own ID, snapshot and session eligibility.

## Platform & lifecycle

### WF-01 — Startup, authentication and authoritative DB

**Actors:** Windows user; platform bootstrap. **Requires:** authorized provisioning/configuration, Git identity/credentials, SQLCipher key and a verifiable dataset. **Requirements:** SYS-001/005/006; COL-001..004/009/011/012.

1. Launch packaged EXE; load paths, logging, config, source/version/package identity.
2. Resolve Git DB repository identity and configured data branch **independently of source branch**; authenticate and fetch remote Git MAIN.
3. Verify accepted remote OID, repository identity, database artifacts, SQLCipher/metadata and migration/schema compatibility for this build.
4. Handle any old runtime DB/WAL/attachments and Recovery notice according to the verified-protection policy; install accepted MAIN into the single active runtime, without merging old unaccepted data.
5. Open domain session and present user login; check credentials and enforce permitted navigation. Initial application mode is READ.
6. Show outstanding Recovery review notice where relevant, without turning old Recovery metadata into an editing/publishing authority.

**Success:** opened authorized READ using authenticated MAIN, no unaccepted writes promoted. **Exceptions:** offline network may permit explicitly verified cached READ, never WRITE; invalid key/schema/remote identity blocks unsafe acceptance; unverified old files must not be deleted; long paths/locks/WAL need verified protection. **Never** force database branch to the name `main_coursefee`. **Code:** `app.py`, `platform/bootstrap/`, `platform/sync/startup_sync.py`, `database/`, `ui/login_dialog.py` (verify exact path).

### WF-02 — READ, Start Editing and WRITE arbitration

**Actors:** logged-in user with mutation capability. **Requirements:** COL-005/006/010, SYS-004.

1. User opens a workspace in READ and may search, view history and export if authorized.
2. User invokes Start Editing; platform verifies accepted remote OID and current local admission/Recovery safety, asks for distributed WRITE lease.
3. If another owner holds WRITE, queue/wait using remote lock/heartbeat/arbitration; show status; no domain business write yet.
4. After grant and revalidation, start durable edit session/recovery journal; UI projects WRITE state and relevant controls.
5. For each save, service validates user's capability and domain-state rule; repository writes transactionally; durable audit/change evidence is recorded.

**Success:** exactly one verified writer; READ users remain readers. **Exceptions:** stale/offline lock or unknown remote state never grants WRITE on a guess; role permission is independent of ownership; lock loss triggers safe state/recovery handling. **Code:** `services/write_transaction.py`, `platform/collaboration/`, `database/mutation_authority.py`.

### WF-03 — Finish Editing / publication and read refresh

**Actors:** writer. **Requirements:** COL-007/010/011, SYS-007.

1. User selects Finish Editing; reject double-completion or invalid local state.
2. Quiesce necessary writers, finalize pending primary domain transactions/audit and durable recovery capture.
3. Verify current remote WRITE owner, lease and accepted base MAIN OID; publish through established Git CAS, not direct arbitrary push.
4. Observe/verify new authoritative remote commit; only then treat publication as accepted, complete journal and release WRITE.
5. Other clients refresh authenticated Git MAIN into runtime in a safe READ transition; derived reports may update separately.

**Failure:** network/remote OID drift/lease expiration, interrupted capture or uncertain publish → preserve original evidence, inform user, do not automatically replay/double-publish. Never mark success solely because local SQLite commit succeeded. **Code:** `services/write_transaction.py`, `platform/synchronization/git_synchronization_provider.py`, CollaborationManager.

### WF-04 — Recovery review, skip and manual reconciliation

**Actors:** user/admin with required access. **Requirements:** COL-003/008/012.

1. Startup/menu discovers authenticated Recovery Cases and notices; display pending count/status, diagnostic category and safe information about source/published state.
2. Open notice/log and compare local evidence against accepted Git MAIN; do not assume differing file hash means a real business transaction was lost.
3. If **Skip**, retain pending notice for future startups; if **Reviewed**, mark that specific case reviewed without rewriting historical evidence or mutating business records.
4. If genuine missed business changes are discovered, manually re-enter through normal Student/Finance/etc service with verified WRITE; check for duplication before re-entry.
5. Maintain archives for audit/restore investigation under security policy.

**Exceptions:** corrupt/unknown case, missing backup, invalid SQLCipher, uncertain publication → clearly surface uncertainty; no automatic database merge, migration stamp, force-push or bypass of write fencing. The presence of Recovery log alone is not supposed to block verified READ; independently unsafe database/remote may still block. **Code:** `platform/write_recovery.py`, `platform/recovery_case_registry.py`, `ui/recovery_cases_dialog.py`, `ui/main_window.py`.

### WF-05 — New machine and cross-machine provisioning

**Actors:** authorized administrator and workstation operator. **Requirements:** COL-001/002/009/010, SYS-001/005.

1. Install clean packaged EXE/ZIP; never ship live center.db, DPAPI secrets or Git PAT inside release ZIP.
2. On clean machine, create/export provisioning request or import encrypted provisioned bundle under authorized process.
3. Bind Git database repository identity + data branch and shared SQLCipher key through workstation-protected configuration; **do not confuse with source Git branch**.
4. First verified MAIN fetch materializes runtime; log in as appropriate user; start in READ.
5. Test WRITE acquisition/release on test/copy before production deployment; verify cross-machine SQLCipher and Git publication consistency.

**Exceptions:** wrong key, wrong private DB repo, invalid bundle, stale secret or unexpected schema → fail safe with actionable re-provisioning; never “fix” by replacing authoritative database. **Code:** `services/git_config_service.py`, `platform/bootstrap/`, `platform/synchronization/`, provisioning Admin tools. **[VERIFY]** Real-machine acceptance and key transfer.

## Student & family

### WF-06 — Student CRUD, family, status and historical views

**Actors:** receptionist/manager/teacher according to capabilities. **Requirements:** STU-001..006/011/012.

1. Open Student Workspace dashboard or list. Normal Student List and Student Overview **default to Active**; user can intentionally choose All or Archived.
2. Search by code/name/guardian contact, apply filters/sort/pagination; exact Student ID is kept for detail navigation.
3. Create/update Student profile and guardian links under authorized WRITE; validate required name, code identity and uniqueness.
4. In Detail view, inspect enrollments, session attendance, assessments, notes, timeline, related financial view.
5. Archive a Student through lifecycle command; archive hides it from normal Active list **but not** historical debt, payment, audit or completed session records. Reactivate explicitly.
6. Export selected/filtered records under permitted READ without altering database.

**Exceptions:** soft-deleted Student, duplicated code, archived class, missing parent, read-only mode → service-specific user-facing rejection. Do not reclassify archived records as deleted. **Code:** `ui/student_workspace/`, `services/student_service.py`, `parent_service.py`, `repositories/student_repository.py`.

### WF-07 — Student Import & Export (full scope)

**Actors:** authorized operations staff. **Requirements:** STU-007..010.

**Import:**
1. Enter Student List → Import (WRITE/capability required); choose **.xlsx** workbook only.
2. File header/column order: Code | Full Name | Preferred Name | Date of Birth | Gender | Status | Level | Notes.
3. Preflight: required full name, optional `HS...` unique code, valid status (ACTIVE/ARCHIVED), date format `YYYY-MM-DD`/supported Excel date, intra-file duplicates and correct template. Show count/errors before mutation.
4. User explicitly confirms; for each valid new Student, preserve supplied unique code or allocate canonical code if absent. Existing code is not overwritten. Record errors and successes.
5. Refresh Student table and show accurate result; close/cancel without imports must **not** be reported as success. Import does not auto-create class enrollment/tuition/debt.
6. **[CODE-OBSERVED]** Some runtime validation/DB errors may lead to per-row partial success after confirmation; document exact success/failure count. Atomic bulk import remains an unapproved separate enhancement.

**Export:**
1. Choose Export Filtered (all matching server pages and sort, including rows not visible on current page), Export All ACTIVE (explicit status), or Export Selected.
2. Check capability and filter total/stable pagination; if result changes during multi-page fetch, fail and ask to retry rather than quietly truncate.
3. Write Excel/CSV only with authorized student fields; export from READ does not acquire WRITE.
4. Do not confuse `StudentRepository.list_active()` (historically only “not deleted”) with strict `Student.status == ACTIVE`.

**Code:** `ui/student_workspace/student_list_page.py`, `ui/students/student_import_dialog.py`, `services/student_import_service.py`, `student_export_service.py`, `student_service.py`.

## Classes, academics and teaching

### WF-08 — Create/update Class and course contract

**Actors:** authorized manager. **Requirements:** CLS-001/006, TUI-002/003.

1. Open Class workspace → list/dashboard → Create Class; provide course/class identity, teacher/cadence and required course fee + planned session count.
2. Validate nonnegative fee, positive planned sessions/cadence, applicable class lifecycle constraints.
3. Persist via ClassService; record fee/history where applicable, audit and refresh Class Dashboard/list.
4. Editing an existing class must not silently reprice historical Enrollment snapshots or posted tuition; effective dates/history are preserved.

**Exceptions:** archived/deleted class, invalid planned sessions, missing course settings, concurrency/permission denial. **Code:** `services/class_service.py`, `ui/class_workspace/`, `models/class_.py`.

### WF-09 — Enroll mid-course, freeze/resume, withdraw and rejoin

**Actors:** manager/reception with enrollment permission. **Requirements:** CLS-002..005, TUI-003/007/010.

1. Open Class detail or Student enrollment view; select exact Student and Class, inspect history.
2. Select effective enrollment start session and optional end session; preview course fee, unit fee, discount, planned eligible sessions and effective range.
3. Validate capacity/active class, duplicate or overlapping live/historical enrollment segments; persist **new Enrollment ID** and agreed tuition snapshot.
4. Teacher/session roster reflects eligibility range; tuition accrual is tied to billable completed sessions within that Enrollment range.
5. On freeze/resume, validate service policy and record explicit exemption/interval; on withdrawal, record effective boundary; on completion, close appropriate lifecycle.
6. On rejoin, restore only when service explicitly permits or create separate historical contract. Never identify all payments by Student+Class only.

**Exceptions:** overlapping ranges, withdrawn/canceled class, archived Student, fee ambiguity, unapproved discount, insufficient capacity. Review retained debt/prepayment before withdraw/rejoin; do not auto-net unrelated enrollments. **Code:** `services/enrollment_service.py`, `class_service.py`, `models/enrollment.py`.

### WF-10 — Archive/restore Class with financial impact

**Actors:** authorized manager. **Requirements:** CLS-001/005, TUI-007/008, FIN-014.

1. Select Class → request Archive; display finance-impact preview including active student/enrollment, outstanding/prepaid and any needed refund review.
2. Confirm with user; lifecycle service records archive and adjusts active roster/enrollment status according to implemented policy, preserving immutable history and amounts.
3. Class no longer accepts normal new teaching/session mutations; related old debt remains available in Outstanding and historical Income.
4. Restore explicitly after validating class lifecycle, not by recreating or deleting financial history.

**Exceptions:** unresolved debt, missing finance snapshot, changed preview between confirmation and commit, concurrent editor. Never silently forgive or transfer debt during archive. **Code:** `services/class_service.py::preview_archive_class/archive_class/restore_class`.

### WF-11 — Schedule and deliver Sessions

**Actors:** teacher/manager. **Requirements:** SES-001/002, CLS-006, TEA-001.

1. Open Class → Sessions → Create Session (number, title, planned date/time, teacher/class context).
2. Save planned session through SessionService under WRITE and permission.
3. During teaching, open exact session; set teaching note/progress and outcomes with explicit Save/Close behavior, using relevant services.
4. Complete/cancel session through allowed state transitions; completion and actual date affect tuition billing eligibility. When Attendance is saved successfully on an eligible Scheduled Session, prompt separately **"Buổi học đã kết thúc?"** default No. Yes invokes permission/WRITE guarded SessionService completion with in-transaction Scheduled/active-class/not-future recheck; No keeps Scheduled. Attendance saving is never rolled back or re-run if completion is declined or fails.
5. Changes update Class/Student projections and timeline; do not mark an unheld/canceled session billable merely because it was scheduled.

5. Class Schedule shows past-dated **Scheduled** lessons, even with no attendance, as a read-only warning list with a Session Status column and a View route. Never auto-finish based only on date or presence of attendance. Cancelled/Postponed are not unfinished-delivery alerts.
6. Session Detail (before tabs) exposes a prominent independent **Hoàn thành buổi học** action for due Scheduled sessions. READ shows the button disabled with guidance, archived history is immutable, and future/Cancelled/Postponed have no completion action. A Completed session shows a green success banner instead. Clicking the independent button re-reads persisted state, verifies roster attendance coverage (warn for unmarked rows and refuse to proceed if coverage cannot be checked), confirms with **No default**, checks live WRITE again and calls the **same** `SessionService.complete_scheduled_session()` used by the post-Attendance prompt. Refresh lifecycle UI and Class Schedule on accepted completion even when dialog is closed with X/Esc. Attendance and accounting are not rewritten by displaying or declining this action.

**Exceptions:** class archived, invalid time range, duplicate/out-of-range session, wrong teacher permission, attempted editing of closed state. **Code:** `services/session_service.py`, `ui/class_workspace/`.

### WF-12 — Session attendance, teaching evaluation, corrections

**Actors:** assigned teacher/authorized operator. **Requirements:** ATT-001..003, TEA-001/002.

1. Open session → load eligible roster using historical Enrollment start/end/withdrawal range.
2. Enter attendance status (present/late/absent/excused as supported) and optional arrival context; batch save through AttendanceService atomically.
3. Add assessments/teaching feedback to appropriate Student/Session identities; save intentionally, not via unsafe unreviewed autosave.
4. On completed Session, TuitionAccrualService delegates chargeability to versioned BillableSessionPolicy: attendance semantics and missing status fallback depend on Enrollment policy version.
5. Correct historical attendance only through valid write state/capabilities, refresh summaries, tuition and reports consistently.

**Exceptions:** student not eligible on session date/number, class archived, session not writable, duplicate/partial batch updates. **Code:** `services/attendance_service.py`, `tuition_policy.py`, `tuition_accrual_service.py`, assessment/teaching note services.

## Course tuition and debts (NOT monthly tuition)

### WF-13 — Contract pricing & accrual by completed sessions

**Actors:** domain service; no separate monthly operator. **Requirements:** TUI-001..004/010.

1. New Enrollment stores agreed course fee, discount, planned eligible session count/range, unit fee and billing-policy version at confirmation.
2. At as-of date, get sessions for exact class/enrollment; exclude future, canceled/uncompleted and out-of-range sessions.
3. For each eligible completed session evaluate `BillableSessionPolicy.evaluate` with attendance if applicable; count billable sessions.
4. Accrued-to-date tuition = canonical billable-session amount after agreed fee/discount policy. Preserve money precision and historical snapshots; no direct FinancePeriod multiplication.
5. Return canonical accrued/unresolved result to Outstanding, Student Finance and report readers.

**Exceptions:** no agreed tuition snapshot, zero/invalid planned sessions, overlapping historical contracts, missing attendance under different policy versions; explicit unresolved outcome, not arbitrary zero. **Code:** `enrollment_service.py`, `tuition_accrual_service.py`, `tuition_policy.py`.

### WF-14 — Collect tuition or other Income

**Actors:** receptionist/finance user. **Requirements:** TUI-005..008, FIN-001..004/009.

1. Select accounting FinancePeriod and Income action. If student tuition, search and select **exact Enrollment** (including old debt if appropriate), not just a Student name.
2. Verify Enrollment balance/identity, payment date, wallet/method, amount, receiver and attachment rights.
3. IncomeService checks WRITE, capability, allowed FinancePeriod/date, exact Enrollment attribution, audit/financial status and stores payment.
4. Wallet is increased for realized ACTIVE Income in its FinancePeriod. Separately Enrollment qualifying-paid total increases for tuition calculation.
5. Refresh Student tuition detail, Outstanding, Income list, Finance Dashboard and reports.
6. Permit valid collection of old debt for withdrawn/archived Enrollment through explicit selection mode; do not require current Student ACTIVE when historic receivable remains.

**Exceptions:** closed period, invalid future payment, nonpositive amount, unmatched Enrollment, ambiguous legacy payment, duplicate submission, denied capability. Do not create a new tuition accrual simply because cash arrived. **Code:** `services/income_service.py`, tuition enrollment picker, Income list/form, `outstanding_service.py`.

### WF-15 — Outstanding, prepaid, refund/credit and historical reconciliation

**Actors:** finance/manager. **Requirements:** TUI-006..010, FIN-014.

1. OutstandingService obtains exact Enrollment lifetime accrued-to-date and qualifying Income/adjustment paid-to-date.
2. Compute and label signed balance: owed (positive), prepaid (negative) or settled (zero), with unresolved exception if contract cannot be priced.
3. Select Open Receivables, Course Balances or Period Activity deliberately; period accounting movements must never be renamed as the entire course obligation.
4. For refund/credit/fee adjustment, preserve original reference and adjustment type, authorize and audit; classify Wallet effect separately from academic credit effect.
5. Archived Student, archived Class, withdrawn/completed and re-enrolled histories remain traceable; do not lose old debt when operational default is Active.

**Exceptions:** voided payment, already refunded credit, duplicate Enrollment, fee-history ambiguity, historical discount mismatch; do not silently apply credits across different enrollments. **Code:** `services/outstanding_service.py`, `tuition_adjustment_service.py`, `income_service.py`, `ui/finance_workspace/outstanding_list_page.py`.

### WF-16 — Tuition history spanning multiple FinancePeriods

**Actors:** finance report reader. **Requirements:** TUI-002/005/009, FIN-001/007.

1. Student enrolls in one course spanning multiple weeks/months; completed sessions accrue course tuition cumulatively under session eligibility.
2. The student may pay partially or in advance in different calendar months. Each Income posts to its actual FinancePeriod, yet relates to the **same Enrollment ID**.
3. Course Outstanding at cutoff uses lifetime accrued/paid for that Enrollment; accounting report for one FinancePeriod shows realized movement in that period only.
4. Do not generate 8/9/10-day per-calendar-month charge rules or quarterly installments in this product. Such a feature is a separately approved new edition/migration.

**Example:** 24-session Enrollment, 8 eligible completed sessions and a partial payment: report earned amount to date and remaining academic obligation separately from cash received during selected accounting period. **Code:** `tuition_accrual_service.py`, `outstanding_service.py`, `finance_period_service.py`.

## Finance Wallet & accounting

### WF-17 — FinancePeriod selection and Dashboard

**Actors:** finance reader/manager. **Requirements:** FIN-001/007/008.

1. Open Finance workspace; resolve currently valid canonical FinancePeriod by effective date, exact start/end and configuration.
2. Navigate Dashboard, Income, Expense, Outstanding, Settlement and Diagnostics with shared period context.
3. Read Cash/Bank realized results and relevant finance projections; these are **accounting** totals, not fresh per-period tuition repricing.
4. Change period to an actual configured period; refresh all dependent panels/exports and indicate closed/no-configuration state.

**Exceptions:** no covering FinancePeriod → explicit “not configured” and restrict operations needing a period, without fabricating one. **Code:** `ui/finance_workspace/finance_workspace_shell.py`, `finance_period_service.py`, `finance_dashboard_service.py`.

### WF-18 — Create/update/void Income and voucher attachment

**Actors:** finance user. **Requirements:** FIN-002..004/009/014, WF-14.

1. Select Income period/filter; create Tuition payment for exact Enrollment or other Income with explicit source and fields.
2. Validate date, amount, method/wallet, identity, permissions and period openness; persist with transaction audit.
3. Upload PDF/JPG/PNG supporting document through FinanceAttachmentService; file stored content-addressed, metadata linked to `entity_type=INCOME`, exact Income ID.
4. On update/void/delete, check closed FinancePeriod/tuition credit impact; preserve historical reference/audit and never silently drop existing evidence.
5. List, detail and CSV/ZIP exports reflect voucher metadata and actual files.

**Exceptions:** missing file, invalid MIME/signature, duplicate file hash, missing receipt, permission denied, locked period. **Code:** `income_service.py`, `finance_attachment_service.py`, `ui/finance_workspace/income_list_page.py`.

### WF-19 — Create/update Expense, personal advance, reimbursement

**Actors:** finance user. **Requirements:** FIN-002..006/009.

1. Select Expense period; create an Expense with payment date, category, description, amount, payment method and funding source.
2. Service distinguishes realized company expenditure from pending/paid-personal advance according to configured funding rules; only realized company-wallet movement hits Wallet/Settlement.
3. When the company reimburses a personal advance, record explicit reimbursement date/source and transition with audit, without double counting the initial personal spend as realized company outflow.
4. Attach invoice/receipt to exact `entity_type=EXPENSE` + Expense ID; changes in attachments do not alter amount.
5. Closed-period, status-reversal, invalid future payment, duplicate or unapproved adjustments are rejected by service.

**Code:** `expense_service.py`, `models/expense.py`, `ui/finance_workspace/expense_list_page.py`.

### WF-20 — CSV export (metadata-only) and ZIP export (real documents)

**Actors:** user with `finance.view`. **Requirements:** FIN-009..014.

**Normal CSV:**
1. Open Income or Expense page; choose exact accounting period/date range/status and search/sort.
2. Click “Xuất CSV”; export **all qualifying transactions**, not only visible page.
3. Include **Transaction ID**, transaction fields, **Voucher Count**, **Voucher Filenames**, **Voucher SHA256**; no absolute machine paths or binary bytes.
4. Represent 0, 1 and many vouchers; sanitize spreadsheet-formula-leading filenames. Read-only export never acquires WRITE.

**Portable ZIP with actual attachments:**
1. Click “Xuất ZIP + chứng từ” in Income/Expense page, same filtering.
2. Generate `transactions.csv`; fetch active voucher rows for exact transaction IDs with bounded batches.
3. Find content-addressed files in authorized runtime or pulled Git repository attachment roots. Check relative paths/no traversal/symlinks, read bytes and validate SHA256.
4. ZIP stores `transactions.csv` plus `vouchers/INCOME_<transaction_id>/...` or `vouchers/EXPENSE_<transaction_id>/...`; preserve identification even when filenames duplicate.
5. Write atomically: if missing/tampered voucher, fail, discard incomplete output, show error. User must not receive “exported successfully” for an incomplete evidence package.

**CSV itself cannot contain PDFs/PNGs**; actual files are in ZIP. ZIP is an evidence copy, not a live file store or restore mechanism. **[VERIFY]** Windows UAT: corrupt file, two same-named vouchers, very large attachments, concurrent exported-row changes. **Code:** `services/finance_csv_vouchers.py`, `income_service.py`, `expense_service.py`, `repositories/finance_attachment_repository.py`, Income/Expense list UI.

### WF-21 — Wallet balance, Settlement draft/confirm/reopen

**Actors:** finance role; confirmation/reopen needs the stronger configured capability/admin rule. **Requirements:** FIN-001..007.

1. Select exact FinancePeriod. Compute complete starting balances and realized CASH/BANK Income/Expense from repositories.
2. Show expected closing balances and enter actual physical Cash/Bank closing amounts; compute differences and require reason where difference nonzero.
3. Save draft without closing ledger.
4. Confirm Settlement with domain permission, audit and atomic snapshot; period then closes normal realized Income/Expense changes.
5. Read/export confirmed history; administrative reopen requires explicit reason, audit and authorized guard; re-evaluate period state.

**Exceptions:** incomplete period, wrong wallet aliases, future transactions, nonmatching dates, another writer, unapproved reopen. Reopen may affect downstream period carry-forward and must be tested. **Code:** `wallet_service.py`, `financial_settlement_service.py`, `finance_period_service.py`.

### WF-22 — Finance Diagnostics, closed-period history and exceptions

**Actors:** authorized finance reader/admin. **Requirements:** FIN-007/008/014.

1. Access Finance Diagnostics under `finance.view` and inspect issue classifications and financial invariant checks.
2. Inspect source entities/transactions for unpaid legacy/unknown funding sources, unmatched enrollment, missing voucher evidence or other emitted diagnostics.
3. Diagnostics only reads and reports; fixes must be separately authorized WRITE business operations with audit.
4. Archived/withdrawn student/class and closed period records remain historically available; do not apply UI Active default as an accounting exclusion.

**Code:** `finance_diagnostics_service.py`, `ui/finance_workspace/finance_diagnostics_page.py`.

## Staff, reports & administration

### WF-23 — Teacher identity, assignments and class access

**Actors:** teacher manager/admin. **Requirements:** HR-001, CLS-006.

1. Open Teacher Workspace; list/search teachers, inspect profile, assigned classes and teaching sessions.
2. Create/update teacher identity with role/service validation and authorized WRITE.
3. Assign/remove teachers to Class via ClassService/assignment boundary.
4. Teacher self-use reads permitted classes/sessions and records teaching activity under attendance/lesson permissions, not global center Finance administration.

**Code:** `ui/teacher_workspace/`, teacher/assignment services, `class_service.py`.

### WF-24 — Employee profile, documents, schedule and working time

**Actors:** employee or authorized HR manager. **Requirements:** HR-002/003/004.

1. Employee Workspace offers manager list/detail and self-service profile as allowed.
2. Manager maintains employment status, job identity and approved documents; employee sees authorized own data and restricted editable personal details.
3. Open expected schedule; record/inspect working time or attendance through owning services.
4. Preserve role separation: self-profile access ≠ other-employee edit; planned schedule ≠ worked time ≠ approved payroll.
5. Lazy-loaded tabs must respect permission, refresh and correct employee identity when navigating.

**[VERIFY]** Payroll rate and overtime calculations require their separate current approved specification; do not invent rates from UI. **Code:** `ui/employee_workspace/`, `services/employee_service.py` and related schedule/working-time services.

### WF-25 — Work registration and review/approval

**Actors:** employee, assigned reviewer/manager. **Requirements:** HR-002/003.

1. Employee submits schedule/work registration with date/time and required context.
2. Reviewer sees submitted registration, checks overlap/eligibility and records approval/rejection with actor and timestamp.
3. Approved registration may inform schedule/working time as the owning service defines; do not implicitly create payroll or cash Expense from an unapproved registration.
4. Corrections/reversals retain audit/history.

**[VERIFY]** Exact state machine/approval permissions depend on current `work_registration` implementation and may be stricter than this conceptual flow. **Code:** `ui/employee_workspace/`; relevant registration service/repository.

### WF-26 — Assessments, learning reports, exports and dashboards

**Actors:** teacher/manager/reception as permitted. **Requirements:** TEA-001/002, REP-001/002, STU-006/011.

1. Record student/session attendance, assessments and teaching notes via owning services.
2. Read Student timeline and dashboards; select target period/student/class as appropriate.
3. Generate/refresh parent-facing student reports or PDF/other authorized exports from accepted source data; no hidden change to tuition or attendance.
4. A post-publish report failure is a derived artifact warning, not grounds to claim an already accepted core transaction failed.
5. Never expose another child's sensitive records without capability.

**Code:** `services/report_service.py`, assessment/note services, `ui/student_workspace/`.

### WF-27 — Admin users, roles, permissions, configuration, audit

**Actors:** authorized Admin. **Requirements:** ADM-001..004, SYS-004/005.

1. Open Administration → Users/Roles; view/create/change account and capabilities via permission service with audit.
2. Change approved application/platform settings, including Git provisioning, only through authorized screens/tools.
3. Access Audit and Diagnostics according to explicit capabilities; do not treat Admin role name as an unconditional bypass of source/service security.
4. Restrict credential/key exposure and preserve source of truth when changing configuration.

**Exceptions:** role conflict, locked user, missing capability, credential/key mismatch, denied WRITE. **Code:** `ui/admin_workspace/`, `services/permission_service.py`, audit/security services.

### WF-28 — Backup, diagnostic, deploy and release acceptance

**Actors:** Admin, authorized maintainer/release owner. **Requirements:** SYS-001/005..009, COL-003/009..012.

1. For backup/export, capture and verify the proper data, WAL/SHM, attachment files, metadata/key provenance and Git OID evidence as required; do not assume a CSV/ZIP financial export is a restorable full backup.
2. On suspected recovery/publish failure, diagnose before discarding local changes; compare to Git MAIN and manually reconcile missing domain operations.
3. Build a clean Windows portable package from **specific audited source SHA**; verify `RELEASE_MANIFEST.json` source commit and packaged Alembic migration head.
4. Test with **copy of real encrypted database**: SQLCipher/DPAPI provisioning, first-start, existing-machine start, READ, Start Editing, one-owner WRITE arbitration, Finish Editing, new MAIN OID, restart.
5. Test finance and teaching domain regression on copied data; verify archived histories, legitimate old debt, Student import/export and CSV/ZIP voucher integrity.
6. Do not deploy a speculative migration or branch guard because CI is green; CI is one gate, Windows on-disk and multi-machine acceptance are separate gates.
7. Record test evidence and PO acceptance before merging/releasing critical change.

**Exceptions:** mismatched source/data branch, earlier broken-source regression, wrong Alembic chain, Windows path-length error, missing attachment, disk full, interrupted publish, old EXE with Git credentials. No silent reset of database to “fix” app startup. **Code:** `build_release.py`, `.github/workflows/`, `platform/sync/`, `platform/write_recovery.py`.

## Startup acceptance matrix — Phase 1 to Phase 5

> This matrix is the required **release acceptance record**, not a claim of test success. Enter PASS/FAIL, Windows EXE source commit, test artifact/log and operator for **every** row before marking the five-phase task complete. Run only on disposable/copied SQLCipher data; never manipulate authoritative Git MAIN or a real production key in fault injection.

| Gate | Exercise | Expected behavior | Evidence status |
| --- | --- | --- | --- |
| A1 | Windows pytest all 3 shards on final release SHA | PASS; all startup fault-injection tests included | PENDING |
| A2 | Cold install, approved provisioning + encrypted copied SQLCipher DB | Login in READ with verified Git DB MAIN identity, not source branch | PENDING — Windows EXE |
| A3 | Existing installation restart after normal Finish Editing | Fetch accepted MAIN, SQLCipher/schema validated, no data loss | PENDING — Windows EXE |
| A4 | Different writer holds remote lease | Start Editing denied/queued; only one verified writer | PENDING — multi-machine |
| A5 | Normal Start Editing → permitted edit → Finish Editing → restart | CAS publication acknowledged, subsequent READ reflects same MAIN OID | PENDING — multi-machine |
| A6 | Interrupted install between snapshot, DB replacement and asset refresh | Original DB/WAL evidence retained, marker replay verified; no unsafe overwrite | PENDING — Windows EXE |
| A7 | Long Vietnamese/nested Employee attachment, locked obsolete rollback copy | Original content intact; accepted MAIN READ not failed merely by obsolete cleanup | PENDING — Windows EXE |
| A8 | Disk full/permission denial **during required backup capture** | Fail-safe preservation and no silent deletion of local unaccepted bytes | PENDING — Windows EXE |
| A9 | Malformed/unwritable Recovery notice and WRITE receipt | If DB/schema separately verified, READ only; no WRITE until valid receipt | PENDING — Windows EXE |
| A10 | Wrong SQLCipher key, identity, branch or incompatible Alembic revision | Refuse unsafe bootstrap; no stamp/forced migration/branch rewrite | PENDING — Windows EXE |
| A11 | Git unavailable but verified accepted CLEAN cached data | Offline READ only; without CLEAN proof fail closed | PENDING — Windows EXE |
| A12 | Build portable EXE; verify full SHA, bundled Alembic, manifest digest and no secrets | Release gate PASS; EXE can open tested copied DB; signer/maintainer records source SHA | PENDING |
| A13 | Read-first docs updated and scope diff reviewed | SYS/COL/START invariants and WF-01..05/28 checked; no unauthorized files | PENDING |

**Phase chain:**
1. Phase 1: baseline tests characterize Windows cleanup failure, crash snapshot and advisory Recovery (test-only).
2. Phase 2: after successful install, stale backup *deletion* faults become deferred cleanup with original evidence retained. Required preinstall capture/rollback failures still stop unsafe replacement.
3. Phase 3: explicit READ-only degradation for unverifiable Recovery receipt, including a process-lifetime READ-only latch which background reconnect cannot clear; recovery requires fresh validated restart, never bypass schema/identity.
4. Phase 4: `scripts/verify_startup_release.py` and `build_release.py` check release SHA, migration asset digest, packaged Git/EXE and secret exclusions before producing a release ZIP.
5. Phase 5: these documents and the Windows acceptance matrix, kept in sync with actual approved behavior.

**Important limitation:** the CI runner and static release gate cannot prove machine-bound DPAPI provisioning, Windows long-path behavior on the operator's machine, a live Git ownership lease or real SQLCipher data compatibility. Do not mark the project complete without Windows test logs and the user's operational acceptance.

## Cross-workflow invariant map — anti-regression guard

| Scenario | Required outcome | Review workflows |
| --- | --- | --- |
| User closes app with Recovery notice | Accepted Git MAIN remains data authority; unresolved manual review stays pending | WF-01, 04 |
| Local file differs from clean receipt | Diagnose/preserve; never assert a lost business row from hash alone; no unverified replacement | WF-01, 04, 28 |
| Another machine currently edits | Current user READ / queue; never dual WRITE | WF-02, 03 |
| Old source branch `main_coursefee` but DB branch `main` | Valid independence; no forced branch rename | WF-01, 05 |
| Student Archived | Hidden from default operational Student list; old class/payment/debt remains queryable | WF-06, 10, 15, 22 |
| Import two existing HS codes | Clearly report duplicates; do not silently overwrite students or create tuition | WF-07 |
| Export filtered with >250 results | Export all qualifying pages or explicitly fail on changed pagination | WF-07 |
| Course spans multiple months | Tuition remains course/Enrollment/session based, FinancePeriod only accounts for payments | WF-13..17 |
| Student withdraws with debt | Preserve exact old Enrollment and collectable debt; new contract remains separate | WF-09, 10, 14, 15 |
| Session canceled by center | Not counted as completed billable session | WF-11..13 |
| Student absent/excused | Apply stored BillableSessionPolicy version, not fixed UI assumption | WF-12, 13 |
| FinancePeriod confirmed | Normal realized ledger mutation denied; permitted read/export unchanged | WF-18..22 |
| Expense paid personally, later reimbursed | No double company-wallet subtraction | WF-19, 21 |
| Income/Expense has two invoices | CSV records both metadata; ZIP contains both actual files | WF-18..20 |
| Voucher missing/modified on disk | ZIP fails rather than claiming successful complete archive | WF-20 |
| Generated report fails after data published | Accepted core transaction remains accepted; separate report warning | WF-03, 26 |
| New build changes schema | Audit migrations/SQLCipher on a copy and Windows EXE before release | WF-28 |

## Developer change-impact worksheet (copy into every PR)

- **Current source SHA / source branch:** ...
- **Configured private DB repository & data branch (separate):** ...
- **Affected requirement IDs:** SYS-/COL-/STU-/CLS-/SES-/ATT-/TEA-/TUI-/FIN-/HR-/REP-/ADM-...
- **Affected workflow IDs:** WF-...
- **Current behavior evidenced by:** exact source files, approved spec, tests, screenshots/logs (state evidence type).
- **Required new behavior:** normal path + edge/historical states + permission + failure/recovery behavior.
- **Out of scope:** migration / Git sync / Recovery / Finance history / unrelated UI refactor, unless explicitly approved.
- **Regression test matrix:** focused tests, Windows pytest three shards, packaged source SHA and UAT when appropriate.
- **Data/invariant checks:** archive/debt, privacy, concurrency, checksum, period identity, historical course snapshots.
- **Documentation update:** both files changed iff contract changed; explain any unresolved `[VERIFY]`/conflict.
- **Release gate:** PR review, CI, owner manual sign-off; do not claim ready before evidence.

## Specific code/spec pointers

- Product and workspace architecture: `docs/Bussiness/ARCHITECTURE_V2.md`.
- Accounting policy: `docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` (excluding superseded tuition-per-period sections).
- Tuition boundary: `docs/finance/FINANCE_WALLET_V2_TUITION_BOUNDARY.md` — explicitly controls course vs FinancePeriod.
- Current implementation details: `src/centermanager/services/`, `repositories/`, `models/`, `platform/`, `ui/`.
- Domain store/head: `migrations/`; secret/SQLCipher boundaries under `src/centermanager/database/`.
- Maintenance rules: root `AGENTS.md`, `docs/AI_COLLABORATION_PROTOCOL.md`.
- These two files are living acceptance references: update them when a product rule changes, not merely on cosmetic code refactors.
