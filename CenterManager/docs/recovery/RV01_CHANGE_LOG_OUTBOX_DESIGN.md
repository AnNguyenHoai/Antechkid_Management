# RV-01 — Durable Session Change Log / Outbox Design
Issue #593 | Date 2026-11-05 | Base: main_repos | Status: PROPOSED — design approval gate, no production changes.

## 1. Business contract

Git MAIN remains authoritative. The purpose of a recovery Change Log is to let staff identify local *committed* work that MAY NOT have reached Git MAIN, not to automatically merge an older SQLCipher DB into newer MAIN. The user can acknowledge "Đã kiểm tra" (reminder stops) or "Skip" (reminder returns next startup). Acknowledgement never deletes backups, writes Git MAIN, or asserts manual re-entry was successful. For financial data, the user must check that the transaction does not already exist on current MAIN before re-entering.

## 2. Proposed storage layers

**Transactional outbox inside SQLCipher**: Create recovery_change_outbox using the SAME SQLAlchemy Session as the business mutation. Required columns: event_id (UUID immutable), operation_id (UUID grouping logical transaction), write_session_id, base_main_oid (full SHA), actor_id, occurred_at_utc, module, action, entity_type, entity_id, related_ids_json (allowlisted identifiers), summary_code, summary_args_json (sanitized), schema_version and db_txn_group_id. Events are facts of an applied SQLCipher transaction; DO NOT write to them from a mere UI Save click. Index by write_session_id and event_id; unique event IDs and retry idempotency need explicit tests. An income payment and its tuition credit may share a logical operation ID but must not create duplicate cash re-entry instructions.

**Durable mirror**: Write append-only/immutable log segments in the sibling .write-recovery directory outside replaceable Git/runtime. Mirror only committed outbox records, through short-lived DB sessions, and fsync/atomic-manifest each segment. Protect confidentiality using encrypted/authenticated storage and existing DPAPI-bound workspace key semantics; never dump plaintext SQLCipher rows, student notes, bank details, credentials or passwords to ordinary text logs. Background mirroring must not bypass MutationAuthorityGate or retain open SQLCipher handles across runtime maintenance. Mirror is an index, not a replacement for the verified backup.

**Recovery Case Registry** (RV-03): Separate persistent cases with case ID, session ID, base MAIN SHA, last observed MAIN SHA, verified capture reference, mirror state (COMPLETE/INCOMPLETE/UNKNOWN), publish outcome (VERIFIED/UNVERIFIED), review state (PENDING_REVIEW/REVIEWED), created timestamp, and schema version. Case records are independent of the live WriteRecoveryJournal and cannot authorize remote publication.

**Publish receipt**: A separate append-only receipt of session_id, exact committed MAIN OID and independent remote observation marks published; do not mutate every outbox event in a second SQLCipher commit. A timeout/ambiguous Git response remains UNVERIFIED unless independently checked. A verified published commit with post-publish local writes is still a distinct unaccepted local risk.

## 3. Crash-order proof obligations

| Window | DB mutation | Outbox | Recovery handling |
| --- | --- | --- | --- |
| Before SQLCipher commit | Not committed | Rolled back with transaction | Do not claim applied |
| After commit, before external mirror | Committed | Committed | Mirror may be incomplete; capture DB/outbox, flag INCOMPLETE, offline inspection later |
| Mirror partial file / crash | Committed | Committed | Ignore unauthenticated partial segment, preserve evidence; never claim complete |
| Before Git commit/push | Local committed | Outbox present | Keep unaccepted capture and base OID |
| Push succeeded but response timed out | Possibly accepted | Outbox present | Check exact remote MAIN; do not assume loss or success |
| MAIN verified, lock release pending | Published | Outbox present | No duplicate manual re-entry instruction based solely on release failure |
| Publish verified then callback wrote local data | Newly unaccepted local mutation | Must have new outbox operation | Preserve separately, do not mark clean |
| New MAIN is A+10, local backup based on A | Old local isolated | Captured outbox retained | Never overwrite A+10, permit manual review and fresh authorized WRITE only |

A file-only journal written before commit creates phantom edits; an event bus/timeline written after commit can miss edits. The proposed outbox solves both at the local transaction boundary. The external mirror is eventually consistent and MUST advertise completeness honestly: either verified watermark/capture or INCOMPLETE. Startup does not need to decrypt old backup on every run; if unreadable, show LOG_UNAVAILABLE and preserve it.

## 4. Domain integration plan (RV-02)

- Income/Expense first: reuse existing transaction-bound AuditService.record_in_session calls; append outbox in same commit for CREATE/UPDATE/VOID/DELETE. Payment-time tuition credit should share operation ID with payment.
- Student: insert outbox before the existing commits in StudentService; do not rely on its post-commit timeline for recovery. Cover create/edit/archive/reactivate/delete/profile attachment.
- Attendance: one grouped event per atomic session-sheet save, inserted before AttendanceService session.commit, with class/session and changed student IDs/count. Teacher notes are sensitive and should not be copied into ordinary logs.
- Enrollment/Tuition: cover enrollment CREATE even without fee override/discount, status changes, withdraw/restore, freeze/resume, agreed fee/credit adjustment, accrued tuition and finance period settings. Some existing audit is conditional or limited to special cases.
- Class archive: one event including affected enrollment IDs and finance impact reference for its atomic withdrawal/archive transaction; class create/update/restore and teacher assignments.
- Attachments: independently audit finance vouchers, profile photos, employee documents, local filesystem rename and Git asset publication ordering. Store hashes and stable references, not the file bytes in the log.
- Admin/users/roles/settings, all background callbacks, repositories, SQLAlchemy Core/bulk, raw DBAPI and migrations: inventory before claiming full coverage. Maintenance/schema changes must not masquerade as user business edits.
- Use source-grounded coverage inventory in RV01_MUTATION_PATH_AUDIT.md; every OPEN item remains a required RV-02 gate.

## 5. Isolation / performance / migration

Current durable WriteRecoveryJournal preserve/verify_capture/reconcile, atomic Git MAIN installation, Git publish compare-and-swap and E1B mutation gate remain unchanged. New outbox inserts must not produce extra network calls on the per-save path. Use bounded async mirroring with backpressure, no new long-held SQLCipher sessions or locks. Record before/after save latency in representative Windows EXE workloads. Prefer one logical event per operation over verbose per-field diffs.

SQLCipher outbox table requires migration and Windows compatibility tests. Older executable without outbox support must be explicitly marked COVERAGE_UNKNOWN and never presented as fully logged. Existing audit may include sensitive free-form details; external recovery summary must use allowlisted structured fields. Verify key access, signed capture, WAL-complete snapshot, copied attachments and rollback on interruption before enabling any new WRITE.

No client from an old session may run a previous publisher or write into a newly installed runtime. Restore/READ/WRITE continuation is delivered only in RV-03 after verification. A fresh WRITE must reacquire exact remote authority, ownership OID and MAIN base; never reuse a stale lease.

## 6. Acceptance / QA plan

1. Failure before commit rolls back business record and outbox.
2. Failure after commit but before mirror can be reconstructed from verified DB/outbox capture; log marked INCOMPLETE if not proven complete.
3. Crash while mirror is writing preserves segment provenance; no corrupt segment accepted.
4. Git push timeout and remote old/new observations yield accurate VERIFIED vs UNVERIFIED state.
5. A-to-A+10 recovery never binary overwrites current MAIN or duplicates finance operations automatically.
6. SQLCipher encryption key unavailable, corrupt journal, symlink or missing manifest fails closed, not silent DISCARD.
7. Student, Enrollment, Attendance, Income, Expense, Tuition and attachments covered by explicit transaction-bound regression tests.
8. Zero automatic database merge, forced remote unlock or bypass of local mutation protection.
9. Recovery cases persist through multiple successful Finish Editing and restart, reviewed state is only user acknowledgement.
10. Legacy EXE/schema, two-machine lock/publish fencing and killed-process/WAL Windows UAT before deployment.

**Approval gate:** RV-01 is a design/audit issue. RV-02 must resolve all OPEN inventory rows with code references before calling its logging complete; do not infer that this targeted repository audit exhaustively traced every write path.

## 7. Design refinements after expanded source audit

**Do not treat all activity as SQLCipher business transactions.** `TuitionAccrualService` is a deterministic READ model; the sources that change accrual include `SessionService` (completion/state/date), `AttendanceService`, Enrollment contract/freeze, and finance adjustments. The recovery report should show these **source commands** rather than generating an event each time a report is recalculated. Similarly `ReportService` deletion writes are a separate projection/artifact safety question.

**Attachments need two-phase provenance rather than a fake single atomic boundary.** `FinanceAttachmentService._store_file` and `EmployeeDocumentService.upload` copy files before committing metadata. SQLCipher outbox is atomic with metadata only, not filesystem bytes. Design a staged-file ledger (temporary reference, expected SHA256, final path, operation ID) with fsync/atomic rename and cleanup rules: orphan files are preserved during uncertain recovery; missing files referenced by a committed metadata row are explicitly flagged. Recovery capture should include or durably reference the complete file set before runtime replacement. Finance voucher SHA naming helps idempotence but does not guarantee metadata and file atomicity.

**Session / finance-period logging is P0, not cosmetic.** A completed teaching session can change outstanding tuition through the accrual read model without any new cash transaction. Finance-period activation/closure changes reporting context. RV-02 must include these sources before declaring the finance Change Log useful to the founder.

**Privilege-based visibility:** Users with permission to view Recovery summary must see only domain events their ordinary role could see; student/finance details may require stricter privileges. A Recovery Case's existence can be shown without exposing private details; the local administrator can inspect a full protected report. No password or authentication secret may be echoed into mirrored log.

**No outbox in READ:** Report refresh and derived projections in READ must not record business event, and auth/login activity should use a separate security audit channel if needed. Explicit system maintenance (migration/bootstrap) uses system mutation permit and should record a technical provenance event, not impersonate an employee WRITE transaction.

## 8. RV-02 targeted implementation matrix and acceptance thresholds

| Rollout slice | Included paths | Mandatory test |
| --- | --- | --- |
| 0: migration + durable primitive | SQLCipher outbox schema/repo + mirror worker + publication receipt | Commit/rollback pairing, WAL kill process, replay proof, legacy schema compatibility |
| 1: finance | Income, Expense, TuitionAdjustment, FinanceAttachment, FinancePeriod | No duplicate finance re-entry; credit+cash same operation; receipt verified with Git MAIN |
| 2: core academic | Student, Enrollment, Attendance, Class, SessionService | Same transaction outbox for state/date changes; grouped session attendance; class archive withdraws |
| 3: personnel + attachments | Teacher, TeacherAssignment, Employee, EmployeeDocument, student profile documents | File/DB crash ordering, orphan preservation, redaction, actor capability |
| 4: remaining repository-wide paths | users/roles/settings, background tasks, SQLAlchemy bulk/raw DBAPI and all GUI entry points | Enumerated call-site manifest and explicit unsupported-path CI failures or bounded coverage declaration |
| 5: release | RV-03/RV-04/RV-05 integration | Startup A+10, Skip/Reviewed, fresh WRITE, EXE two-machine crash/UAT |

No slice should claim end-to-end completeness until slice 4 (or accepted explicit exclusions) is verified. Documentation and targeted source review on this PR do **not** constitute an exhaustive repository scan.

### Risk acceptance gates for founder

- **Data priority:** no automatic merge; manual re-entry allowed, but the user must see a warning that events are potentially unaccepted, not proven absent from MAIN.
- **Safety priority:** if backup cannot be verified, the app cannot discard it for convenience; non-blocking startup applies only after safe isolation.
- **Operational priority:** do not make every Save wait for Git or remote checks; write local transactional event and mirror asynchronously with a safe final fence.
- **Compatibility:** do not deploy a schema-changing outbox until older Windows EXEs' behavior has been tested; older sessions must not be permitted to publish incompatible authoritative databases.
- **Exit criterion for RV-01:** founder approves this design and the coverage-gap inventory as the input plan for RV-02; RV-02 must prove remaining OPEN paths before promoting logging as complete. GitHub issue #593 should not auto-close from a partial implementation PR.


## 9. Further source-verified requirements: security events, non-DB writes, and existing mutation-intent ledger

### Three distinct event types — do not conflate them

1. **Business committed event** (new transactional SQLCipher outbox): user-recoverable facts, recorded in the exact same DB transaction as a successful business change. The user-facing report displays sanitized summaries only.
2. **Forensic mutation intent** (already implemented in `database/guarded_dbapi.py:121-196`): AES-GCM encrypted and fsync'd statement/parameters **before SQL execution**, intentionally retained across rollback. It cannot prove successful commit. **Never replay it or display raw SQL/parameters to users.**
3. **Security/system/file provenance**: role/password/session authentication, config.json modifications, migrations, source document copies. These do not all share ordinary business SQLCipher commit boundaries; use a separate privileged journal or explicit staged-file receipt, always excluding secrets.

This is a key simplification: do **not** rewrite low-level guarded_dbapi to serve as the user's Change Log. Its forensic intent data are sensitive, potentially expensive and may include rolled-back writes. The business outbox should be a compact independent record emitted from trusted service transaction boundaries.

### Highest-risk uncovered routes

- `PermissionService._audit()` is best-effort **after** business commit using a separate `AuditService.record()` transaction. Move an appropriate security metadata event inside the original transaction; avoid password/hash data. `update_user_role()` currently labels a role change as `USER_UNLOCKED`, so existing audit action names require semantic review before reuse.
- `ConfigurationService.save()` changes config.json using `save_config()` without a SQLCipher commit. The DB outbox cannot cover config changes; decide if such config is Git-authoritative or machine-local. Do not capture Git tokens, credentials, or DB encryption data. A protected config change receipt can be emitted after atomic file write and validation, but a crash before it needs a separately verifiable file-level checkpoint.
- `EmployeeScheduleService` has **mixed coverage**: regular rules/exceptions/assignments direct commits without observed audit, while publish/freeze/reopen calls `_audit_week()` within transaction. Apply outbox to direct commands, reuse in-session audit where present.
- `EmployeeWorkRegistrationService` does use in-session audit for the examined commands. Do not record a second falsely independent business edit from its timeline.
- `SessionNoteService` and `AssessmentService` mutate valuable teaching records without verified in-session audit; prioritize concise identifiers to support manual checking.
- `StudentDocumentService`, `TeacherDocumentService`, `EmployeeDocumentService` are file-before-DB. A DB outbox describes committed metadata, but a separate file manifest/capture must preserve bytes and detect staged orphans.
- `StudentImportService` may call ordinary services repeatedly, producing a **partially successful import**. Recovery should show batch ID plus successful item IDs; do not mark entire Excel import applied merely because the dialog closed.

### Coverage verification process for RV-02

An implementer must check the current repository's full Python tree with an AST/static manifest rather than assume only service names examined in RV-01 exist. Scan `services/`, `repositories/`, `ui/`, `database/`, `platform/` and native Git/SQLCipher adapters for: `commit`, `flush`, `bulk_save_objects`, `bulk_insert_mappings`, `bulk_update_mappings`, `execute`, `executescript`, `sqlite3.connect`, `os.replace`, `shutil.copy*`, raw `write_bytes/text`, Git publication, and background delayed callbacks. Annotate each detected path as BUSINESS, DERIVED, SYSTEM or FILE with reviewed owner and test IDs. Any new business command missing an outbox hook must fail a targeted regression gate. Automated detection is only a candidate index; it cannot by itself prove that every mutation is transactionally logged.

**Review status remains OPEN until** (1) the complete call-site manifest is verified (not merely a sample), (2) privacy and retention are explicitly approved, (3) Windows CI passes, and (4) compatibility and performance verification plans are accepted. No premature `Closes #593` in PR body.
