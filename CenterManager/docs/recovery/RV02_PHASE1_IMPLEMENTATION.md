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
