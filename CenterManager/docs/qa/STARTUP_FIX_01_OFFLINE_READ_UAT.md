# STARTUP-FIX-01 — staged Offline READ / reconnect UAT and safety gate

## Scope

- PR #605: Phase 1 local cached READ eligibility with CLEAN receipt + runtime hash + SQLCipher + signed Git DB identity + WAL and recovery guards.
- PR #606: Phase 2 offline bootstrap, read-only Alembic check, no daily report/migration/forced-password mutation, READ-only UI and WRITE admission fence.
- PR #607: Phase 3 background reconnection without relying on manifest version; pull-only MAIN install, exact independently observed OID and CLEAN receipt before releasing offline fence.
- PR #608: Phase 4 expanded regression tests and this UAT/runbook.

These PRs are stacked. Merge in the order #605 -> #606 -> #607 -> #608 after green CI on each **current head** and Windows EXE UAT. Never cherry-pick Phase 3 without the Phase-2 fence.

## Hands-on Windows EXE tests (required; not automated by CI)

1. On test clone with published CLEAN status, launch normally online, log in as a READ user, close EXE. Disconnect Internet entirely and launch again. Verify banner *Offline READ - cached data* and familiar Student/Finance read screens. **Start Editing** must be disabled; clicking via keyboard / shortcut also must not acquire WRITE.
2. With offline read active, verify Student Profile, Enrollment, Tuition, Expenses, Attendance, reports can be **viewed** but no SQL mutation, export-time migration, online permission elevation, or remote push occurs. Record a hash of `center.db` pre/post, allowing only ephemeral read-related OS sidecars if documented and audited.
3. Re-enable Internet while EXE remains open. Allow background health/remote fetch, verify exact accepted MAIN commit and runtime database. Confirm state becomes ONLINE READ and then test an authorized Start Editing, Finish Editing and a second machine pulling changes.
4. Advance remote MAIN without increasing manifest runtime_version before reconnect. Verify remote commit difference still triggers a full pull and DB/GUI refresh.
5. Simulate GitHub auth failure, remote timeout, invalid branch, mismatched signed DB identity, changed local DB checksum, missing DB key, pending OPEN/RECOVERY_REQUIRED and live WAL. Expect **no fallback** when provenance/recovery is untrusted. For remote connectivity/credentials failure with valid cache, READ may be offered but WRITE must remain denied.
6. Interrupt process during MAIN install and restore connection. Verify startup install marker/recovery guards prevent use of an incomplete workspace. Do not delete marker or recovery evidence.
7. Disconnect while in an active EDITING transaction and verify the existing lease expiry/recovery protocol remains authoritative. Do not interpret it as a clean Offline READ handoff; do not silently drop or publish unaccepted edits.
8. Test signed/verified schema at the bundled Alembic head, then simulate cache with older revision. Offline launch must **refuse schema mutation**; online controlled migration is unchanged.
9. Confirm local password login works with cached users and local lockout. Users with mandatory password change should be told they need authoritative WRITE online; no shared password mutation offline.
10. Test fresh Windows machine without accepted cached SQLCipher DB: offline launch must fail safely without creating a new collaboration database.

## Automated acceptance checklist

- [ ] All three Windows pytest shards green at current #605 head.
- [ ] All three Windows pytest shards green at current #606 head.
- [ ] All three Windows pytest shards green at current #607 head.
- [ ] All three Windows pytest shards green at current #608 head.
- [ ] Complete Windows EXE test matrix above, including two-machine Git MAIN advance.
- [ ] Review local logs for accidental SQLite write, credential disclosure, Git push, identity pin advancement and unaccepted recovery cleanup.
- [ ] Founder signs off; only then mark PRs ready for review and merge serially.

## Known operational boundary

Offline startup is deliberately **fail-closed**, not a second authoritative source. A valid cached snapshot is permitted for READ; **no offline editing** is added. A resumed network connection alone is not acceptance; fresh MAIN verification and a valid CLEAN receipt are both required before WRITE becomes available.
