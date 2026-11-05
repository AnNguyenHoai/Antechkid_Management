# RV-01 — Mutation Pathways and Recovery Change Log Audit
Date: 2026-11-05  •  Issue: #593  •  Base: `main_repos`  •  Classification: P0 design gate

## Decision, evidence standard and scope

**Decision proposed:** reuse the existing transaction-bound `audit_logs` for business-readable descriptions where available; add a *new immutable recovery outbox record in the same SQLCipher transaction* at uncovered mutation boundaries, then mirror it durably outside the replaceable runtime before the application is allowed to classify an incident as fully described. A recovery notice reports **operations potentially not accepted by Git MAIN**, not confirmed loss. **No automatic merge**. The implementation is deferred to RV-02/03/04.

This is a **targeted source audit** of listed production files on `main_repos`, not proof that every module/SQL statement in the entire repository has been inspected. Any row marked OPEN / NOT VERIFIED is a release gate for RV-02, not implied coverage. GitHub code search returned no indexed results for the broad terms in this session; therefore the inventory was traced via exact repository files instead of assuming complete search coverage.

## Verified production architecture

| Layer | Source evidence | Observation |
| --- | --- | --- |
| Audit model | `models/audit_log.py:8-25` | `audit_logs` has actor/action/module, target/entity identity, summary, result, arbitrary details; **no session ID, operation ID, base MAIN OID, publish OID or mirror acknowledgment**. |
| Audit service | `services/audit_service.py:28-70` | `record_in_session()` adds a row to caller transaction; `record()` separately commits. Only the former is necessarily atomic with a caller business change. |
| Business SQLAlchemy | `database/session.py:206-215` | `session_scope` commits/rolls back; services also own explicit commits. Commit must be traced at concrete service boundaries. |
| Mutation authority | `database/mutation_authority.py:91-132,245-308` | Local gate validates WRITE authority/session/actor before protected mutations. An outbox must not bypass gate with a second DB writer. |
| Cross-process maintenance | `database/session.py:93-205`, `database/engine.py:98-120` | SQLCipher handles and maintenance fence protect runtime DB installs; no mirror worker may retain a live DB handle across replacement. |
| Recovery | `platform/write_recovery.py:319-340,494-590,592-635,770-794` | Existing journal, `preserve()`, `verify_capture()`, `reconcile()` protect local workspace and verify publish. Capture includes WAL-complete DB and selected files and is **not** itself a user-facing per-operation log. |
| Startup | `platform/sync/startup_sync.py:86-191,319-382,498-573` | Fetch remote MAIN, preserve unaccepted workspace through reconciliation, then atomic install. Reuse, do not replace with unconditional reset. |
| Publish | `platform/synchronization/git_synchronization_provider.py:1324+`, `services/write_transaction.py:953+` | MAIN publish uses expected commit and remote verification. Timeout may mean UNKNOWN even if commit reached remote. |

## Concrete mutation-path coverage matrix

Definitions: **ATOMIC** = confirmed audit row added to the *same* database transaction as this particular business change; **AFTER-COMMIT** = event/timeline generated after DB commit and may be missing after a crash; **PARTIAL** = some but not all actions have audit; **OPEN** = not yet traced and cannot be called covered.

| Domain | Entry/commit evidence | Existing recovery-readable audit | Gap and RV-02 requirement |
| --- | --- | --- | --- |
| Income | `services/income_service.py:515-590,618-749,915-925,931-1020,1047-1081` | **ATOMIC** `_record_audit()` before commit for CREATE/UPDATE/VOID/DELETE; tuition payment + adjustment audit in same transaction | Audit lacks WRITE session, op ID and accepted publish OID; establish event grouping for combined cash+credit transaction. Post-commit timeline/events are non-authoritative. |
| Expense | `services/expense_service.py:226-263,365-421,445-490` | **ATOMIC** create/update/void/delete audit before commit | Same metadata/mirroring gaps; finance audit must not imply external banking reconciliation. |
| Enrollment | `services/enrollment_service.py:427-489,565-595,784-809,856-882` | **PARTIAL**: transactional audit for discount/fee override, freezes and some restore/status paths; simple enrollment CREATE audit is conditional on discount/override | Mandatory base CREATE / status transition / withdrawal/change fee event, including cases without discount; audit conditional repository-provider feature flags. |
| Tuition | `services/income_service.py:618-749`, `services/enrollment_service.py:437-489,565-595` | **PARTIAL ATOMIC** payment-credit, enrollment tuition overrides and freeze events | Inventory outstanding tuition config/accrual/adjustment services and UI direct writes remains OPEN; multiple entities per financial operation must share operation ID. |
| Student | `services/student_service.py:89-136,171-227,266-379,381-435` | **AFTER-COMMIT**: timeline/event dispatch after `session.commit()`; no `AuditService.record_in_session` in inspected service | Crash after commit but before timeline can omit change; add transactional recovery outbox for create/edit/archive/reactivate/delete/profile attachments. Do not log raw personally sensitive fields by default. |
| Attendance | `services/attendance_service.py:294-395,397+` | **AFTER-COMMIT**: one SQLCipher transaction for sheet (`session.commit()` line 386), then timeline/events after commit (`_publish_session_save_side_effects`) | Add **one grouped outbox operation** per atomic sheet save containing session/class ID, changed student IDs/count (avoid dumping teacher notes), status delta summary. Handle zero-row/no-change saves. |
| Class | `services/class_service.py:178-249,353-494,595-671,939-979` | **AFTER-COMMIT**: class create/archive/restore timeline after commit; archive mutates multiple enrollment rows in one transaction | One operation per class/archive with affected enrollments and finance impact reference; avoid duplicate per-row manual re-entry advice. |
| Attachments | `services/student_service.py:230-264` and `platform/write_recovery.py:494-590` | **OPEN** file-to-DB ordering and orphan creation/deletion not yet exhaustively audited | Inventory profile pictures, finance vouchers, employee docs and Git attachment sync. Store references/hash, not file content in logs; prove journal captures necessary assets. |
| Users / roles / settings | `services/audit_service.py:76-82` exposes `log_user_action`/`log_role_action` | **OPEN** specific calling flows and transaction boundaries not verified | Establish actor/permission audit, authentication maintenance exclusions; preserve privacy and do not store password hash/token in change log. |
| Background, reports, migrations and raw SQL | `database/mutation_authority.py:311-345`, `database/engine.py:98-120` | **OPEN** path-by-path coverage not proven | Enumerate service/repository/SQLAlchemy bulk/DBAPI writes before RV-02; classify derived reports as regenerable and maintenance separate from business edits. |

### Safety-critical counterexample

`StudentService.create_student` commits at `student_service.py:123`, then calls timeline at 126–133. `AttendanceService._save_session_attendance_atomic` commits at `attendance_service.py:386`, then sends side effects at 394. A crash in between leaves the business row but not necessarily the human-readable timeline. Reading only timeline/events cannot reconstruct every unaccepted edit. Conversely an event fired before a failed commit is not proof of an applied write. This is why the outbox must share the SQLCipher commit.

## Mandatory continuation before RV-02 implementation

1. Search **all** service modules and repositories for `commit`, `flush`, bulk SQL, SQLAlchemy Core writes, raw SQLCipher/DBAPI mutations, UI/background callback persistence. The table above is a verified starting matrix, **not a 100% complete inventory**.
2. For each row, document actor/session source, permission, transaction owner, audit placement, attachment ordering, generated IDs, idempotency and rollback behavior. Distinguish business mutations from report/cache maintenance.
3. Verify tuition accrual, adjustments, invoice/expense details, archived class rollback, teacher scheduling, employee docs, finance period settings, custom SQL and admin actions. Unverified means coverage unknown; do not mark release complete.
4. Regression test every business entry point actually exposed in Windows EXE. Include aliases and alternate repository implementations.
5. Prove a new outbox writer cannot write during READ/lease loss or emit a log saying APPLIED for a rolled-back operation.

## P0 failure modes to prohibit

- A durable recovery manifest without matching committed DB/outbox data must be marked **INCOMPLETE**, not “all changes recorded”.
- External audit file written before the DB commit must not be treated as applied. Use transactional outbox for applied facts.
- A second SQLCipher commit solely to write a log is **not** atomic with the original business commit.
- Git MAIN changed A→A+10: never overwrite remote with B nor assume every B event is missing; report requires manual re-entry review against MAIN.
- Post-publish report generation may mutate local derived data; do not treat all derived churn as business edits; retain existing journal rules until independently audited.
- A Python event bus or timeline emitted after commit is for UI/report notifications, not a durable recovery authority.
- No recovered data may be published by replaying a stale lock or reusing an old publisher; new WRITE session requires fresh remote session+OID and MAIN CAS.


## Expanded mutation inventory — pass 2 (source read on main_repos)

This section resolves several OPEN items from the first pass. A service being free of AuditService imports in the inspected source is **evidence only for that service**; it does not prove that no SQL trigger, generic persistence hook or UI wrapper records a separate audit.

| Domain | Verified commit path / lines | Finding | Priority for transactional recovery event |
| --- | --- | --- | --- |
| Finance periods | `services/finance_period_service.py:168,196` | Period creation/closure commits directly; no in-transaction AuditService call was found in inspected file. Finance period boundaries affect reporting. | P0: create/close, date coverage and inactive status |
| Tuition adjustments | `services/tuition_adjustment_service.py:229-247,287-299` | Refund and credit adjustment paths use `AuditService.record_in_session()` before transaction commit, with idempotency key. Audit already atomic; enrich with session/op metadata rather than duplicate business event. | P0: finance operation grouping |
| Tuition accrual | `services/tuition_accrual_service.py:1-21` | Explicit **deterministic read model**, not persisted. No independent accrual Change Log event needed; log mutations to source Enrollment/Session/Attendance/Income/Adjustment. | DERIVED / no separate write log |
| Teacher | `services/teacher_service.py:93-138,184-279,287-331` | Create/update/archive/restore commit then dispatch EventBus. No in-transaction AuditService call found in inspected file. | P1: teacher identity and status changes |
| Teacher assignment | `services/teacher_assignment_service.py:31-79,79-107` | Assign/unassign commits then publishes change event. No in-transaction AuditService call found in inspected file. | P1: teacher/class assignment |
| Teaching session | `services/session_service.py:99-140,170-262,286,301-316` | Create/update/state/delete direct commits. Session is input to tuition accrual; after-commit EventBus is not durable evidence. | **P0**: completed/cancelled dates and teaching session state |
| Employee | `services/employee_service.py:141-145,182-221,223-275,299,308-351` | Employee create/update/account link/status changes commit directly; legacy self-identity repair is a specially authorized system mutation. No transaction-bound AuditService call found in inspected service. | P1: employee/role/account link; special maintenance excluded from normal WRITE event |
| Class timeline | `services/class_timeline_service.py:30-57` | Separate `session.commit()`, often invoked after parent ClassService commit. **Not atomic** with class mutation. | DERIVED historical UI; cannot substitute outbox |
| Teacher timeline | `services/teacher_timeline_service.py:30-57` | Separate `session.commit()` after teacher/assignment operations. | DERIVED historical UI; cannot substitute outbox |
| Reports | `services/report_service.py:259-284` | Report deletion may mutate report metadata (and unlink generated report files). Must classify whether specific report files/metadata are fully regenerable; not all filesystem writes equal business changes. | OPEN classification; protect source attachments |
| Employee documents | `services/employee_document_service.py:145-194` | **Copies file to runtime before DB metadata commit** at line 181. Crash can leave orphan file. No transactional audit in inspected path. Must include both file and metadata in recovery provenance. | P0 attachment lifecycle; file-first recovery |
| Finance vouchers | `services/finance_attachment_service.py:172-225,228-252` | SHA-named file is copied atomically before DB metadata commit; `AuditService.record_in_session` follows file storage and precedes commit; removal soft-deletes metadata, preserves file. | Existing audit ATOMIC for metadata. Need file/capture integrity, orphan detection, and file reference in event. |

### Expanded risk demonstrations

**Teaching-session→tuition impact:** `TuitionAccrualService` is calculated from sessions/enrollments/attendance, not persisted. Therefore a teaching session marked completed in `SessionService` may change accrued debt even if no direct tuition row is written. The log must report the **source session change**; logging only an income/tuition adjustment misses it.

**File-before-DB windows:** `EmployeeDocumentService.upload()` and `FinanceAttachmentService.add_attachment()` stage a file *before* metadata commit. If DB commit fails or process crashes, the staged file can remain unreferenced. A database-only outbox is insufficient to prove that the recovered capture contains all business attachments. Record staged file SHA/reference and verify it during recovery; do not delete an apparently orphaned file until provenance is established.

**Read-model distinction:** `TuitionAccrualService` should **not** emit a new financial event every time a debt number is calculated; this would create false unaccepted changes from READ. Report/cached projection writes must be treated separately from business transaction logs.

### Coverage follow-up still OPEN (must resolve before RV-02 general rollout)

1. Repository-wide enumeration of source files and write sites is not provided by the connector's indexed search (broad search returned empty). The inspected named files are confirmed; **additional service directories, UI direct SQL, background tasks, SQLAlchemy Core/bulk and raw DBAPI operations remain unverified**.
2. User/role/password/permission and settings mutation ownership must be traced from actual UI/service symbols, not inferred from the `AuditService.log_user_action` helper alone.
3. Employee, schedule, work registration and finance document lifecycle includes module-specific paths not exhaustively discovered. Audit all live EXE entry points before claiming complete coverage.
4. Some existing `AuditLog.details` include free-form input; external mirror must not dump these fields.
5. Logging every SQLAlchemy flush/commit indiscriminately may include maintenance and derived/report operations and would be misleading. Require domain annotations at business operation boundaries.


## Expanded mutation inventory — pass 3: full repository tree discovery, UI routing and low-level intent recorder

A successful GitHub tree listing for `main_repos` returned **1,638 tracked objects (not truncated)**, including **164 Python UI modules** and the actual service filenames. This resolves the earlier inability to enumerate names through unindexed code search. **It does not prove every file's contents were read.** Targeted verified sources below are explicit; remaining files require automated code coverage in RV-02.

### User, role, settings and UI evidence

| Component | Code reference | Classified status | Consequence |
| --- | --- | --- | --- |
| User/role service | `services/permission_service.py:57-70,164-214,353-535` | **AFTER-COMMIT best-effort audit**, separate `AuditService.record()` transaction | Change of role/user may commit while the audit insert fails or process dies; recovery outbox must be inside actual management transaction. |
| Role-change audit semantic error | `services/permission_service.py:371-386` | **PROVEN BUG in current audit label**: `update_user_role` commits role change then emits `USER_UNLOCKED` | Never build Recovery Report directly from action string without fixing/normalizing; record distinct USER_ROLE_CHANGED event. In RV-01 document, do not silently change production. |
| Login / password | `services/permission_service.py:264-346` | Protected authentication uses `LocalLoginState` outside shared DB; legacy login may commit account state; `change_password` uses `verified_self_password_change` permit | Password change needs **redacted security event** if covered; no password, hash, token, login credentials in any mirrored Change Log. Login throttling telemetry is *not* a normal business edit. |
| Configuration | `services/configuration_service.py:29-36`, `ui/admin_workspace/settings_page.py:267` | Config JSON `save_config` on disk, **not SQLCipher transaction**; WRITE/outbox DB hook alone cannot cover it | Need separate protected-file provenance/atomic replace and an admin CONFIG_CHANGED record; check authority/rollback and whether Git MAIN owns this config. Do not log Git token or connection secrets. |
| User UI | `ui/admin_workspace/user_list_page.py:158-224` | UI routes user writes through `PermissionService`, no direct SQLAlchemy commit observed in inspected file | Gap is **service audit transaction**, not duplicated UI log. |
| Settings UI | `ui/admin_workspace/settings_page.py:218,267` | UI delegates saves to `ConfigurationService` | Outbox cannot automatically cover filesystem-only settings changes. |
| Finance period UI | `ui/finance_workspace/finance_period_config_dialog.py:86-136` | UI delegates period configure/deactivate to service | Focus on `FinancePeriodService` transactional logging. |
| Session note UI | `ui/session/session_note_widget.py:263-270,314` | Delegates to `SessionNoteService` | Service commits notes; content may contain PII. Use entity ID + action only for ordinary Recovery Report. |
| Student image and documents UI | `ui/student_workspace/profile_image_dialog.py:125-146`, `ui/student_workspace/documents_widget.py:178-200` | Delegates to Student/StudentDocumentService | File-first and DB metadata reconciliation needed; do not log bytes or full paths. |
| Employee schedule UI | `ui/employee_workspace/employee_schedule_widget.py:590-865` | Service calls for seed, assignments, publish/freeze/reopen and rule/exception CRUD | Need outbox for all schedule lifecycle writes; no direct UI commits observed in this inspected module. |
| Admin data reset UI | `ui/admin_workspace/data_management_panel.py:117,182` | Delegates preview/reset to `AdminDataReset` | Treat mass reset as **one privileged grouped operation** with affected counts; avoid dumping individual PII. |

### Additional service coverage

| Component | Evidence | Status / disposition |
| --- | --- | --- |
| Parent | `services/parent_service.py:86-122,139-219,237-246` | Create/update/delete direct commits, no in-session audit observed: **P1**, privacy protected |
| Assessment | `services/assessment_service.py:86-127,160-231,245-253` | Assessment create/update/delete commits: **P0 academic evidence**, must log metadata not raw scores/notes by default |
| Session note | `services/session_note_service.py:52-101,110-184,188-195` | Create/update/delete commits: **P0** due to teaching progress; sensitive content redacted |
| Student note/highlight | `services/student_note_service.py:42-110`, `services/student_highlight_service.py:18-66` | Create/update/delete direct commits: **P1**, do not mirror free-form content |
| Student documents | `services/student_document_service.py:37-96` | File copied before DB commit; document deletion changes DB separately: **P0 attachment provenance** |
| Teacher documents | `services/teacher_document_service.py:54-136` | File copied before DB commit: **P1 attachment provenance** |
| Employee schedule | `services/employee_schedule_service.py:140-239,436-550,553-636` | Rules/exceptions/assignments/seed direct commits; weekly publish/freeze/reopen calls `_audit_week()` before commit. **PARTIAL audit coverage**, not entirely absent. |
| Employee work registration | `services/employee_work_registration_service.py:83-144` | Actions create/update/delete/submit/accept/reopen/deadline/close use `_audit()` -> `record_in_session()` before commit: **ATOMIC metadata audit** for inspected paths. |
| Employee working time | `services/employee_working_time_service.py:91-155` | Booking/check-in/check-out/approval/lock direct commits: no transaction-bound audit observed: **P1**, potential payroll impact |
| Employee admin management | `services/employee_admin_management_service.py:102-118,159-170,204-220` | Employee/registration deletes use transaction-bound `record_in_session`: **ATOMIC** for inspected paths |
| Enrollment transfer/reconciliation | `services/enrollment_transfer_service.py:335-358`, `services/enrollment_reconciliation_service.py:224-239,324-347` | Uses transaction-bound audit for inspected mutations: **ATOMIC**, ensure grouped operation IDs and no duplicate manual re-entry |
| Financial settlement | `services/financial_settlement_service.py:173,310-334,395-423` | Lifecycle audit uses `_record_transition_audit` in caller transaction; some draft mutations must be verified separately. **PARTIAL** pending full per-method proof |
| Admin data reset | `services/admin_data_reset.py:223-240` | Transaction-bound audit after destructive business deletion, **ATOMIC** at inspected boundary; recovery report should summarize privileged reset, not individual rows |
| Student import | `services/student_import_service.py:38+` | Excel bulk import delegates to other methods (needs final call-path proof), do not assume atomic batch just from absence of commit in importer |
| Teaching assessment, assignment, parent/notes | Above | Additional classes of unaccepted business data that earlier RV-01 draft had not enumerated |

### Low-level SQL / safety-critical observation

`database/guarded_dbapi.py:121-196` **already records encrypted mutation intents** to `WriteRecoveryJournal().root / 'mutation-intents'` using AES-GCM, fsync, SQL and parameters, with session and mutation-gate incarnation. It records a statement in a progress handler **before the first VM instruction** to survive later rollback or process failure. The project already has a local forensic intent ledger.

**Important: an intent is not a committed operation.** Its rows may correspond to statements that subsequently fail, roll back, or have no net effect. It can contain sensitive SQL parameters and must **not** be printed into UI Recovery reports or used as user-readable applied-change evidence. This mechanism is complementary to a transaction-bound **business outbox**, not a substitute. Reusing/replacing it requires a separate security and disk-retention audit; do not double-log full SQL or expose its contents.

`database/guarded_dbapi.py:223-226` validates commit authority at low level. `database/mutation_permissions.py:9+` maps table actions to permissions. `database/migration.py:143-185` executes Alembic with `system_mutation_permit('migration')`; `database/seed.py:19-131` bootstraps roles/permissions. These are privileged **system maintenance** changes, not ordinary user recovery events. Direct `executescript`, Core bulk SQL and database authorizer must stay protected by existing mutation gate.

### Concrete issue flagged for RV-02, NOT modified here

**`PermissionService.update_user_role()` emits `USER_UNLOCKED` after role update.** It is both a misleading action name and a best-effort post-commit audit. The fix should move a correctly classified role-change event into the same transaction and test it; separate security audit logging can remain compatible. Do not fix by simply renaming emitted text in the external Recovery Report.

### Scope / confidence note

Git tree discovery allows an exact repository inventory. Targeted UI/service/DBAPI reads above establish verified specific call paths. A completed **machine-wide, all-file static AST scan** is not yet performed, and some repository paths may mutate through SQLAlchemy Core, trigger, migrations, native or background code. The RV-02 rollout must run a mechanically reproducible audit and CI coverage gate over the complete repository before claiming completeness; do not infer “everything covered” from these inspected examples.
