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
