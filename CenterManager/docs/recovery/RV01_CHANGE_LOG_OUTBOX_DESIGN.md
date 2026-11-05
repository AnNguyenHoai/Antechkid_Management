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