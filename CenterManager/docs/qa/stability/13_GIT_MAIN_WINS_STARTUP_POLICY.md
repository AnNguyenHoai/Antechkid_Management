# Production change — Git MAIN wins local startup (2026-11-02)

Founder policy: the official Git remote MAIN is authoritative; unaccepted local work may be replaced on startup. This deliberately supersedes the prior E1B-1/QA-S01 rule that all unpublished local changes must block startup indefinitely.

## Safety boundary
- Do not apply this policy during an active local editing session; this entry point is startup only.
- The local Git repository must connect, fetch and independently observe the same remote MAIN OID. If either observation fails or differs, **stop before reset**.
- For dirty legacy or pending journal, existing `WriteRecoveryJournal.reconcile` creates and verifies an immutable recovery capture *before* Git reset; it does **not** publish local data or claim WRITE authority. If preservation fails, startup refuses to overwrite.
- After a verified reconciliation receipt, Git repository reset uses existing flow.
- Startup SQLCipher installation stages and validates the accepted DB first; quiesces runtime handles; moves existing DB and WAL/SHM/journal out of the live namespace; atomically replaces DB; validates checksum; rolls back on install failure. The caller refreshes sessions and checks identity/manifest through existing preflight.
- No remote WRITE lock release, force revoke, Coordinator or hosting introduced.

## Test scope and unresolved coverage
New `tests/test_qa_git_main_startup_policy.py` checks mismatched Git proof refusal, legacy reconciliation ordering, and replacing a disposable local sqlite file with stale WAL. These tests do not simulate complete packaged EXE migration, a remote branch that changes between fetch and reset, or a recoverable filesystem crash during sidecar rename. Existing tests asserting legacy startup refusal need review against this explicit revised policy; do not silently edit all E1B-1 recovery tests.

**Risk / release gate:** Startup now accepts loss of unaccepted local work as requested. The retained recovery capture offers forensic fallback but is not published automatically. Real Windows SQLCipher upgrade UAT, normal startup when no local repo exists, rollback on post-install metadata/refresh failures and exact-head CI must be reviewed before production deployment. This PR is Draft until those gates pass.


## Follow-up source impact audit while CI #884 runs
- **TOCTOU #1 (confirmed source gap, patched):** the previous reset path fetched a second remote MAIN after startup proof, permitting commit drift. Startup now pins the verified SHA and confirms the remote still matches after reset; if not, it refuses runtime installation. Additional regression cases added.
- **Post-install rollback #2 (confirmed source gap, patched):** the first implementation deleted old DB/WAL backups immediately after atomic file replacement. A later attachment/manifest/session-refresh/receipt error could leave failed startup with a newly installed DB and no rollback generation. Backups are now retained until all startup gates succeed; failed gates invoke database rollback. A disposable rollback regression was added.
- **Still outstanding:** manifest and attachments currently update separately from database. A post-install failure can leave metadata or attachment mirrors inconsistent even if DB rollback succeeds. This remains a release blocker pending a cohesive rollback/staging design or verified acceptance tests.
- **Still outstanding:** legacy journal reconciliation may depend on a readable SQLCipher key and materialization contract. Test a real prior EXE workspace copy; do not assume the synthetic SQLite smoke test covers it.

CI #884 belongs to the initial PR head, not the subsequent audit commits; final approval needs exact latest head results.
