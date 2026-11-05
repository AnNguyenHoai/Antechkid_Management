# RV-02 Phase 1 — Implementation and release gate

**Issue:** #594. **PR:** #599. **Status:** implementation slice awaiting Windows CI and broader RV-02 coverage. **Do not close issue from this PR.**

## What this PR actually implements

| Layer | Source | Behavior |
| --- | --- | --- |
| SQLCipher data | `models/recovery_change_event.py`, migration `1e10a045` | New additive `recovery_change_outbox` table storing UUID event/operation, verified WRITE session, base MAIN OID, actor ID, business entity ID, action and allowlisted summary identifiers. No raw notes/SQL/tokens/payment details. |
| Capability gate | `database/mutation_permissions.py` | The outbox is an aggregate side-effect authorized by the originating business WRITE capability, not a new independent WRITE privilege. |
| Runtime context | `database/engine.py`, `services/recovery_change_outbox.py` | Only authoritative runtime engines generate business events; isolated mutation-protected test/maintenance engines do not. Production events require journal OPEN and no authority loss. |
| Atomicity | `services/recovery_change_outbox.py` | Outbox rows are inserted in the **same SQLAlchemy/SQLCipher session and commit** as business data. Rollback removes both. No network calls or extra SQLCipher commit. |
| External mirror | `platform/recovery_change_mirror.py` | After successful commit, short-lived SELECT of recorded events and immutable AES-GCM segments under sibling `.write-recovery/rv02-committed-events/<session>`. If key/disk/mirror unavailable, user transaction remains committed and recovery must assess mirror **INCOMPLETE** using preserved DB. |
| Completeness | `assess_mirror_coverage` | Only attested, complete SQLCipher session outbox can establish COMPLETE; missing/tampered encrypted segment is INCOMPLETE, unverifiable source is UNKNOWN. |
| Publish outcome | `platform/recovery_publication_receipt.py`, `write_recovery.py` | After `WriteRecoveryJournal.published()` verified remote MAIN OID, persist HMAC-signed session→MAIN OID receipt. Timeout/unknown publish does not create a verified receipt. Receipt failure does not overwrite authoritative Git truth. |
| Selected business hooks | Income, Expense, Student, Attendance, Session, Enrollment, Class, FinancePeriod, TuitionAdjustment | Events inserted in caller transaction and mirrored only after successful commit. One event per changed attendance sheet; class archive event includes withdrawn count; finance refunds/credits use IDs only. |

## Safety decisions / non-goals

- **Never automatically merge or replay these events into Git MAIN.** They are for human manual review and re-entry.
- Existing Git MAIN compare-and-swap, remote WRITE lock, Recovery Journal, SQLCipher/WAL fences and mutation authorization remain authoritative.
- A failed post-commit mirror **must not** be presented as a failed student/finance transaction. Later Recovery Case creation compares captured SQLCipher outbox against mirror to show COMPLETE, INCOMPLETE or UNKNOWN.
- The new table is additive; legacy EXEs **do not** write it, so old client sessions must be reported `COVERAGE_UNKNOWN`. Old EXE compatibility and actual two-machine UAT remain blockers before release.
- No RAW SQL intent log is used for user-facing recovery summaries. Existing `guarded_dbapi.py` encrypted intents are pre-execution and may be rolled back.
- External mirror key is loaded from the existing protected SQLCipher key store; no key in Git, plaintext log, or UI.
- This phase does **not** include RV-03 case registry, startup popup, automatic reconciliation or opening WRITE after recovery; those are separate issues.

## Required follow-up RV-02 slices (not yet implemented)

The RV-01 inventory contains **116 explicit business/admin commit candidates**, plus direct SQL, callbacks and file operations. This PR covers the specified core paths but is **not full coverage**. Remaining high-risk scope:

1. PermissionService role/user/password changes (best-effort post-commit audit and mislabeled role change), FinanceAttachment and all document/file metadata paths; handle file-before-DB crash window.
2. EmployeeWorkRegistration, EmployeeSchedule, EmployeeWorkingTime, Teacher/TeacherAssignment, Parent, Assessment, SessionNote, StudentNote/Highlight, EnrollmentTransfer/Reconciliation, financial settlement, admin reset.
3. Dynamic UI/background/Core SQL/DBAPI and every allowed exception from `RV01_COMMIT_SITE_REGISTER.md`; add CI-enforced coverage ledger and end-to-end call-path tests.
4. Verified real Windows EXE SQLCipher/WAL kill-process tests, migration/schema compatibility with legacy EXEs, Git timeout response loss, session authority loss/reconnect, benchmark of synchronous per-operation encrypted mirror and disk retention policy.
5. Privileged reader for recovery event summaries (RV-03/04), with permissions for finance/student data and an explicit warning that `UNVERIFIED` does not mean missing from MAIN.

**No premature auto-close:** PR description is `Refs #594`, not `Closes #594`. Issue #594 remains OPEN until all acceptance criteria and Windows UAT are satisfied.

## Test gates in this PR

`tests/test_rv02_recovery_change_outbox.py`: same-transaction commit and rollback, duplicate UUID replay prevention, sensitive argument rejection, real SQLCipher/WAL commit without mirrored segment, protected-runtime journal binding, mirror failure after commit, HMAC publication receipt validity/tampering and mirror completeness source attestation.

**State of CI:** look up current PR #599 head workflow; never infer PASS from previous commit. No production deployment until all Windows shards and packaging UAT pass.


## Phase 2 expansion on the same draft PR — source audit ledger (2026-11-05)

The source hooks were expanded beyond the original Phase 1 slice to **29 application service files** (according to the GitHub changed-file inventory). New committed operation categories include:

| Group | Source-level integration | Remaining proof required |
| --- | --- | --- |
| Academic | Assessment, SessionNote, StudentNote, StudentHighlight | End-to-end protected SQLCipher READ/WRITE permissions; privacy and process-kill tests |
| Students/family | Parent, StudentDocument | Attachment file integrity and file-before-DB crash recovery; notes remain redacted |
| Staff | Teacher, TeacherAssignment, Employee, EmployeeWorkingTime, EmployeeSchedule, EmployeeWorkRegistration | Exact capability and rollback tests; week-seeding without assignments, payroll and attendance implications |
| Staff admin | EmployeeAdminManagement | Reopen registration period and protected deletions; transaction grouping |
| Finance | FinancialSettlement, FinanceAttachment | Financial duplicate detection and signed publish verification; voucher bytes require separately verified capture |
| Identity/security | PermissionService CREATE/UPDATE/DELETE user/role and password reset metadata | **Self-password-change and legacy authentication intentionally excluded** from normal outbox: these run special authentication/local-state permits and must not write plaintext secrets or bypass E1B; role-change audit label corrected |
| Enrollment correction | EnrollmentTransfer, EnrollmentReconciliation | Grouped source/target IDs and idempotent finance reconciliation; never auto-replay |
| Destructive admin | AdminDataReset | One event after audited bulk deletion, while outbox table remains in PROTECTED_TABLES |

A dedicated source-order regression test `tests/test_rv02_domain_outbox_hooks.py` verifies the first seven domain slices place the outbox call **before** their existing DB commit and mirror **after** it. Other services are exercised by existing Windows CI and require targeted integration tests in a later QA pass before release.

### New safety regression: reusing a SQLAlchemy session after rollback

The recorder's Python `session.info` may still hold a pointer to a rolled-back outbox object. It must **not** mirror this object if a later unrelated operation commits on the same Session. `mirror_after_successful_commit` now checks event IDs against committed DB rows via `session.get()` before mirroring, and a dedicated test verifies the rolled-back event never appears in the encrypted mirror. This is a real crash/transaction provenance safety fix, not an optimization.

### Remaining RV-02 release blockers

- **DO NOT MERGE** while latest Windows CI has not conclusively passed; previously passing CI on older head does not prove these new hooks compile or retain API behavior.
- **DO NOT CLOSE #594** or add `Closes #594` until complete coverage and UAT are certified.
- File-first uploads, document deletion ordering and orphaned file bytes are **not** fixed by metadata-only outbox hooks. RV-02 attachment provenance must verify actual SHA256, relative path, and capture completeness independent of the DB event index. Existing student-document delete unlinks file before DB commit; this is a separate data-loss ordering gate.
- `ConfigurationService.save()` mutates machine-local JSON, not the SQLCipher business transaction. Config secrets should never enter the business outbox; a separately authenticated safe-file provenance contract is needed if configuration needs Recovery.
- Native DBAPI/SQLAlchemy Core/SQL triggers may not emit domain hooks. The existing guarded_dbapi mutation-intent ledger and E1B-2B local authority gate remain essential, but encrypted *intent* is not proof of committed edits.
- Legacy EXEs do not emit the new table: coverage must remain `UNKNOWN`, never `COMPLETE`. Validate schema compatibility before a production migration.
- Performance and Windows SQLCipher/WAL kill-process, two-client, publish timeout, lease-loss and backup-restart UAT must pass.


## Performance optimization — asynchronous encrypted mirror (RV-02, 2026-11-05)

### Save-path contract

The business operation and recovery outbox **still share one SQLCipher commit**. Following that commit, `mirror_after_successful_commit` verifies each event ID against the committed SQLCipher outbox, serializes minimal allowlisted metadata and enqueues **immutable bytes**. It does **not** load the encryption key, invoke AES-GCM, create files or call fsync on the Save thread. `recovery_mirror_worker.py` performs these operations with a bounded (512-item) dedicated daemon worker; it never accesses DB sessions, recovery journals or Git refs.

This change is deliberately a **risk-limited first optimization**: preserve the one-file-per-event immutable mirror format and its existing tamper/coverage semantics instead of introducing a new batch-file schema before Windows UAT. Physical batch segments and key-cache optimization may follow after benchmarks demonstrate a need.

### Failure and barrier contract

- Queue full: refuse additional mirror work immediately, flag incomplete and keep the SQLCipher outbox. Never block Save until disk becomes available.
- Worker exception: log incomplete; never propagate an exception that falsely reports a successful business commit as failed.
- Abrupt process termination while worker is pending: externally mirrored history may be incomplete, but existing Recovery Journal **must** preserve a WAL-consistent SQLCipher database with committed outbox events. RV-03 must compare the protected snapshot to mirror and disclose INCOMPLETE.
- Finish Editing: after the local Save/gate finishes, but **before** `preserve('before-publish')`, call `drain_before_capture(timeout_seconds=5)`; update journal `rv02_mirror_state` to `QUEUE_DRAINED` or `INCOMPLETE`. `QUEUE_DRAINED` certifies ONLY worker queue processing, **not** completeness of all committed events. Do not silently treat it as `COMPLETE` without offline snapshot attestation.
- If drain times out or fails, proceed through the **existing protected SQLCipher recovery capture**, not a new unsafe Git publication or an optimistic mirror-complete claim. The background worker never retains an open DB handle during runtime replacement.
- `async Save` is not equivalent to `async SQLCipher commit`: transaction atomicity, WRITE authority and rollback semantics are unchanged.

### Windows latency and QA

Run `python tools/benchmark_rv02_mirror.py --samples 50 --json rv02-mirror-benchmark.json` locally. Windows CI shard 0 runs the same synthetic microbenchmark and publishes its JSON artifact. Metrics: synchronous per-event AES-GCM+fsync median/P95 versus async enqueue median/P95, plus total wall-time until all mirrors are durably written.

**Limitations:** This benchmark is *component-only* and excludes SQLCipher commit/read, Qt event loop, Git operations, startup, backup copy, antivirus variability and EXE packaging. Targets for actual Windows EXE UAT: Save P95 regression <=10%, normal startup P95 regression <=5%, zero main-thread encrypted-mirror fsync, no unaccepted edits silently marked fully logged. Do not claim these targets achieved from the component microbenchmark alone.

Tests: `tests/test_rv02_background_mirror_worker.py` injects stalled storage, full queue, worker errors and immutable byte copies; updated existing outbox tests wait through a bounded drain barrier. `test_rv02_recovery_change_outbox.py` continues checking SQLCipher WAL commit and rollback durability.


## Phase 2 safety hardening — session-isolated mirror drain and legacy schema regression

Audit found a real cross-session reporting defect: the asynchronous mirror worker originally kept only a **global** failure counter. If WRITE session A had one failed mirror, a later fully mirrored WRITE session B still returned `INCOMPLETE` from `drain_before_capture`. That was a false cross-session contamination and could unnecessarily slow or alarm Finish Editing.

- `recovery_mirror_worker._MirrorWorker` now maintains independent submitted/completed/failed counters keyed by exact `(recovery_root, write_session_id)`. Global worker statistics remain diagnostic only.
- `record_for_active_write`'s post-commit handoff passes the authenticated event's `write_session_id` to the queue.
- `WriteTransactionManager._publish` drains only the active Recovery Journal's session from that root, after WRITE quiescence and before protected pre-publish capture.
- `tests/test_rv02_background_mirror_worker.py` adds regressions for prior failed session versus new successful session and a stale other-session blocked disk write. An actual task queued ahead in the same single worker may still delay new-session mirroring; the 5s bounded barrier remains and protected outbox capture must be retained.
- A new `tests/test_rv02_migration_compatibility.py` checks additive schema creation without changing legacy business records and confirms migration downgrade refuses to discard committed outbox history.

**Not covered by these synthetic tests:** Windows EXE schema handoff from an older published MAIN, 2-client old EXE write fencing, real SQLCipher physical WAL checkpoint under process kill, attachments staging, and actual startup/Save P95. Those remain mandatory release gates.

**CI gate:** latest PR #599 head must be verified with all three Windows shards PASS; a prior PASS on `5a9bf566` does not validate this new worker version.


## Verified Windows component latency evidence

In previously completed Windows runner workflow [#42006247444](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/42006247444), the **microbenchmark step passed**, even though that workflow's overall shard 0 pytest failed an unrelated mocked employee-registration test (later fixed in subsequent PASS run). With 50 synthetic AES-GCM mirror events:

| Metric | Median | P95 |
| --- | ---: | ---: |
| Synchronous per-event mirror (crypto, new file, fsync) | 5.676 ms | 10.181 ms |
| Async Save-path queue submit | 0.008 ms | 0.012 ms |

End-to-end asynchronous submission for 50 events: 1.316 ms; until all 50 mirror files were encrypted and fsynced: 678.329 ms. These numbers describe **the mirrored-event component only** and must not be extrapolated into an end-to-end application latency speedup percentage. Worker session-scoping was added after this run; it must pass its own CI.

Actual Windows EXE Save/startup and Finish Editing P95 with old/new binaries, SQLCipher encryption, file attachments, anti-virus and user-class sizes remain unmeasured.


## RV-02 Step 1 integrity audit — operation dedupe and DB→mirror crash boundary

**Baseline:** Previous head `90e1b853` Windows CI `42031103845` PASS (3/3). New tests/schema changes require their own green CI.

**P0 finding A — retry operation-id reuse could create duplicate confirmed events.** Before this audit, `event_id` was a PK, but `operation_id` had only a non-unique index. A retry with the same operation ID and a new event ID would therefore append a second committed event. The additive migration and ORM index now enforce `UNIQUE(operation_id)`; a duplicate aborts the **whole caller-owned business transaction**, not just the event insert. This is **duplicate suppression / fail-closed behavior**, not a claim that a failed retry automatically returns the previous successful result. A future UI-level idempotent-result lookup must not authorize new mutations.

The current design records **one recovery event per operation ID**. If a future operation needs multiple events sharing a transaction operation ID, introduce a separate event ordinal and explicit operation grouping contract rather than quietly removing uniqueness. Migration `1e10a045` is not yet merged/deployed; schema changes here must be retested on Windows EXE and remain blocked if existing DBs already contain duplicate operation IDs.

**P0 finding B — committed SQLCipher row can outlive missing external mirror.** The crash window between `session.commit()` and worker fsync is unavoidable without synchronous mirror IO. This is safe **only if** an authenticated WAL-complete protected SQLCipher capture is retained. The real SQLCipher WAL test now asserts a committed business row and outbox row remain available while no encrypted external mirror exists; an attested source yields `INCOMPLETE`, while unattested source yields `UNKNOWN`. A crash cannot be called fully mirrored on queue status alone.

**Evidence and limitations**
- `test_rv02_recovery_change_outbox.py`: operation-id uniqueness with fresh event ID; full business rollback on conflict; encrypted SQLCipher WAL crash gap; mirror completeness/UNKNOWN.
- `test_rv02_migration_compatibility.py`: additive migration has a **unique** operation index and preserves legacy business rows; downgrade with committed outbox refuses destructive deletion.
- Existing E1B recovery capture uses `runtime_database_publication_snapshot()`, validates SQLCipher artifact and hashes all included files, and writes an HMAC-signed manifest. Do not bypass those source-of-truth checks when RV-03 presents an event list.
- The process-kill boundary with Windows packaged EXE, old-client schema and multi-workstation runtime replacement are **still outstanding**; tests above are injection/synthetic, not EXE certification.
- Known limitation: per-entity source hooks cannot prove every lower-level DBAPI/SQLAlchemy Core/file-only write is represented. Full completeness must be attested against a verified captured SQLCipher source and the RV-01 mutation register; an old EXE without the table is `UNKNOWN`.
