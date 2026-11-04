# Git MAIN authoritative startup — operator policy (2026-11-04)

## Business decision
Git `main` is the only accepted operational database. Changes made while holding WRITE are provisional until a verified successful Finish Editing publication. If the app crashes, is killed, or is restarted before publication, local edits **may be permanently discarded**. Operators agree to re-enter those edits.

## Startup contract
1. Keep the single-runtime-process lock and local mutation gate closed.
2. Require a successful Git fetch and a fresh independent observation of exactly the fetched MAIN commit.
3. Reset local Git worktree to that pinned commit, without ever pushing local edits. Discard untracked local worktree files.
4. Validate the authoritative encrypted DB and install it with existing crash-safe startup backup/rollback, WAL/SHM isolation and SQLCipher re-open verification.
5. Re-observe remote MAIN after installation; require exact pinned Git HEAD/upstream, clean worktree, no WAL, and exact runtime-vs-repository DB hash.
6. Only then atomically write a new CLEAN publication receipt. The old journal (including an unreadable or OPEN journal) must not authorize old data to be pushed.
7. Any failure aborts startup/synchronization with WRITE denied. Never replace a database when remote MAIN is unavailable or cannot be observed.

## Remains unchanged
- Exactly one holder of WRITE at a time; queue/lease/renewal/release policy.
- Remote MAIN publication compare-and-swap and authoritative source validation.
- Local mutation authority gate and encrypted DB requirements.
- Atomic DB installation and crash rollback.
- Finish Editing retries and reconciliation when outcome is UNKNOWN **within the same running process**.

## Deployment gate
Do not merge or deploy based only on source review or unit tests. Perform the Windows two-client UAT stated in the PR, including power-loss/kill and remote advancement. Upgrade all clients to the same compatible EXE/package. Back up the full runtime + `.write-recovery` sibling before first rollout; this backup is a manual safety net, not automatic replay.

## Deliberately not claimed
- A lost local session is recoverable after restart.
- READ from an unverified/empty local DB when Git is offline.
- A local report file is authoritative.
- A new EXE may safely be mixed with legacy clients that can publish MAIN.
