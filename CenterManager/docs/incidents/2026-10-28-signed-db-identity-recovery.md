# P0 recovery runbook — authoritative database identity mismatch

## Incident
The 2026-10-28 CenterManager log reports that Git publish succeeded, but a following startup/write-handoff rejected the database: `Authoritative database bytes do not match the signed identity manifest`. The app intentionally fails closed.

## Immediate containment
1. Stop all CenterManager writers; no Finish Editing, archive, restore, or direct writes.
2. Preserve immutable copies of the **data** repository (not the application source repository), including relevant commit SHAs, `database/center.db`, `database/center.db.identity.json`, and `manifest.json`, plus workstation runtime DB, WAL/SHM where present, local pin state, and logs. Avoid putting keys or plaintext student data in issues, PRs or CI artifacts.
3. Never delete the local identity pin, regenerate workspace keys, disable validation, or rewrite the data Git MAIN branch as a shortcut.

## Read-only forensic validation
For each candidate data commit (last known bootable and failed published version):
- Extract the DB, identity sidecar, and runtime manifest from the **same exact commit**.
- Calculate DB SHA-256 and compare with `identity.payload.sha256` (no key required for this first check).
- Using the **existing provisioned workspace key on an authorized machine only**, authenticate identity HMAC and database encryption and run SQLCipher `PRAGMA integrity_check`.
- Compare database_id/generation to locally pinned identity, ensuring no generation rollback.
- Produce row counts and business diffs for classes, enrollments, sessions, attendance, tuition, payments, and outstanding balances, without exposing PII.

## Recovery decision
A. If the failed DB is valid and independently verified as the intended published bytes, recover via a controlled, reviewed publication transaction that creates the matching authenticated identity with unchanged database_id and strictly monotonic generation. Prove on a test workstation first.
B. If DB bytes are corrupt or provenance cannot be established, restore the last trusted artifact and reconcile transactions since that version from authoritative records and backups.
C. If identity is intact but local pin shows a newer generation, stop: investigate rollback/conflicting writers, do not clear pin.

## Release gate
- CI passes new publish regression and existing security/fencing tests.
- Publish a class archive in a disposable encrypted test workspace.
- Cold-start a second client, start editing, finish editing, and cold-start again.
- Verify finance/class lifecycle and all audited record counts.
- Only after sign-off run production recovery with audit trail and rollback materials.

## Source-code fix in this PR
`WriteTransactionManager._publish_database_and_manifest` now calls `materialize_runtime_database_to_repository` so a WAL-safe database snapshot and signed sidecar are installed together. `GitSynchronizationProvider.publish_only` verifies the authoritative database before staging any Git commit. This prevents recurrence but does **not** repair already-published corrupted/mismatched data.
