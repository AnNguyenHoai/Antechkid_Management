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


## Further audit — missing clone and multi-artifact atomicity (release blockers)
- **P0 missing repository bootstrap:** `StartupSynchronization.run` clones before it can check the new Git-authoritative startup policy. Existing `GitSynchronizationProvider.clone()` invokes `require_replaceable()` before cloning; for a legacy local database with no journal/repository it can still reject initialization. The new authorization is therefore not complete for a replaced EXE with a fresh runtime folder or missing `runtime/repository`. Do not remove this guard without an offline preclone capture strategy and a verified remote ref.
- **P0 recovery receipt mismatch across partial failure:** startup `reconcile` writes a RECONCILED receipt before actual reset. If Git reset succeeds but database install/manifest update fails, the next startup must validate current fingerprint and retained captured generation. A successful DB-only rollback does not revert Git repository or its receipt. Existing tests do not establish a fully transactional recovery after all such failure orders.
- **P1 cross-artifact skew:** `_sync_employee_attachments_from_repository` deletes the runtime attachment directory before copy and has no rollback; manifest and metadata version are truncated/overwritten independently. On failure after DB replacement, the DB may be restored but attachments/manifest may be at the new generation. This contradicts a single accepted application snapshot.
- **P1 untracked data:** new pinned `git reset --hard <SHA>` does not remove untracked files. Existing receipt verification may continue failing even though Git MAIN is authoritative; destructive cleanup must only happen after a verified immutable backup and must not remove any recovery captures.
- **P1 stale remote after last observation:** origin can advance after the second `ls-remote` while local installation proceeds. Pinning the SHA avoids installing a different commit; policy must specify whether any stale-but-previously-accepted SHA is permissible or whether startup requires latest remote at unlock. Do not claim strict latest HEAD under races without final check.

**QA decision:** HOLD pending above P0 blockers and Windows SQLCipher UAT; ongoing CI passing alone does not establish startup correctness. Avoid deploying current Draft to real production.


## Scoped preclone path implementation
A missing local Git repo with existing runtime DB now gets a verified sibling `runtime.write-recovery/preclone/<uuid>` file copy with SHA256 manifest **before any clone**. The only new clone exception is the explicit `preclone_capture` option; it validates the copy, the unchanged original file bytes, expected runtime roots and absence of another journal/repository before proceeding. Normal clone invocations retain the existing `require_replaceable` guard. The saved copy is not treated as a remote publication and is not automatically deleted.

Additional tests exercise missing-repo preservation and passing the scoped capture into clone. The existing incomplete nonempty repository still fails closed, and any inability to capture files must block startup.

**Reminder:** release still requires exact-head CI and real Windows SQLCipher UAT; the current draft is not approved for rollout. Cross-artifact attachment/manifest failure atomicity remains pending.
