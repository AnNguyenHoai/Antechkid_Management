# Git MAIN Wins — Windows EXE Upgrade UAT Gate

Base: PR #546; CI #914 PASS at `0e8d3da42fe60430e8da050f31bb4d9eb5a5f12f`. This checklist is **not a record of UAT execution**. Run only on disposable copies of known production-like SQLCipher workspaces. Never run a test EXE on the live operational runtime or official production Git credentials.

## Prepare
1. Close CenterManager on the test machine. Copy its **entire** runtime directory and its sibling `runtime.write-recovery` folder into a separate test area on the same filesystem. Record SHA256 of `runtime/Database/center.db`, any WAL/SHM, manifest and attachment files.
2. Set the cloned workspace's Git origin to an isolated throwaway remote containing an authorized synthetic database snapshot, not production MAIN. Use test-only credentials, no WRITE lease shared with production.
3. Confirm SQLCipher key availability and encrypted database integrity; record the synthetic authoritative MAIN SHA and expected database identity/generation.

## UAT scenarios and required observations
| Case | Input | Expected |
|---|---|---|
| U01 | Legacy runtime DB differs from Git MAIN, no journal | Preserve local receipt/capture, validate exact remote MAIN, install Git MAIN |
| U02 | Valid local WAL/SHM with unaccepted changes | WAL never replays into authoritative database; preserved copy retains evidence |
| U03 | Git unavailable / remote SHA mismatch | No destructive replacement; startup blocks |
| U04 | Missing local repository and existing DB | Local workspace backed up and SHA-verified before isolated clone |
| U05 | Crash/fault during DB swap | Old database and WAL recoverable; next startup fails closed or completes safely |
| U06 | Failure during Employee attachment copy | Startup rejects; database, manifest, metadata and attachment set must remain internally consistent |
| U07 | Failure during manifest/version update | Startup rejects; no mixed-generation visible workspace |
| U08 | Remote WRITE session belongs to another client | Startup must not revoke/release that session |
| U09 | Repeated successful startup | Same Git MAIN identity/generation; no accumulating unverified journal states |
| U10 | Two test EXEs / queued WRITE handoff | No stale DB, queue owner or UI state after handoff |

## Objective evidence
Save logs, Git SHA at each verification boundary, hashes before/after, journal status, SQLCipher integrity results, and captured exceptions. Record EXE build SHA, Windows version and filesystem volume. Never publish a test recovery capture or paste tokens/keys into tickets.

## Explicit release blockers
- Current `_sync_employee_attachments_from_repository()` deletes old Employees attachment mirror before copying new files. It has no rollback. Existing `_apply_runtime_database()` also updates manifest and metadata independently. The DB-only rollback may therefore leave mixed versions on U06/U07. **This remains a P1/P0 release-risk gate despite CI #914 passing.**
- Synthetic unit tests do not substitute for encrypted Windows EXE UAT.
- Do not merge/deploy PR #546 until U06/U07 failure handling is made transactional or the team explicitly accepts and documents the operational recovery procedure.

## Commands for branch QA
`cd CenterManager && python -m pytest tests/test_qa_git_main_startup_policy.py -v`

`cd CenterManager && python -m pytest -q`
