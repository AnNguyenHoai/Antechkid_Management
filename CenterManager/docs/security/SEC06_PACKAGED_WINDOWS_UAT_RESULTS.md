# SEC-06 Packaged Windows Adversarial UAT — Execution Record

## Scope

This record executes the packaged-Windows portion of SEC-06 after the automated adversarial gate in PR #439 passed and was merged. It is an evidence record, not a substitute for the automated tests.

## Baseline

- Base branch: `main_repos`
- Automated adversarial gate: PASS (PR #439 merged)
- Happy-path packaged Windows restore: PASS
- Runtime DB ownership/Windows handle recovery fix: PASS in packaged restore
- Target: packaged Windows CenterManager application using the normal encrypted production workspace

Before executing U01-U10, record the exact application commit/build SHA and Windows version below.

| Field | Value |
|---|---|
| Application commit/build SHA | PENDING |
| Windows version | PENDING |
| Tester | PENDING |
| Date/time | PENDING |

## Safety rules

1. Use a disposable UAT workspace or retain a separately verified known-good backup before destructive fault injection.
2. Never copy workspace keys, passwords, tokens, decrypted DB contents, or DPAPI material into this evidence file.
3. For each negative test, verify both the immediate error and the post-failure state.
4. After U01-U08, execute the restart verification from U10 before marking the case PASS.
5. A case is FAIL if the application silently falls back to plaintext, silently regenerates a key, mutates the live DB before authorization/validation, leaves the runtime DB unreadable, or leaves an undocumented split-brain state.

## Execution matrix

| ID | Test | Result | Evidence / observation |
|---|---|---|---|
| U01 | Tampered encrypted backup | PENDING | |
| U02 | Wrong workspace key | PENDING | |
| U03 | Corrupted encrypted DB | PENDING | |
| U04 | Unauthorized direct restore | PENDING | |
| U05 | Failure while preserving live DB/metadata | PENDING | |
| U06 | Failure after DB install before metadata completion | PENDING | |
| U07 | Post-swap DB validation failure | PENDING | |
| U08 | Publish/refresh failure after restore | PENDING | |
| U09 | Repeated valid restore in one process session | PENDING | |
| U10 | Restart verification after negative cases | PENDING | |

## U01 — Tampered encrypted backup

Procedure:
1. Create a valid backup through CenterManager.
2. Record a harmless sentinel value in the current live workspace so it is easy to prove whether restore changed the live DB.
3. Copy the backup to a disposable test copy inside the managed backup area if the product workflow requires it.
4. Modify one byte of the backup `center.db` without updating the manifest/checksum.
5. Attempt Restore using the normal UI and valid administrator authorization.
6. Confirm Restore is rejected for integrity/checksum validation.
7. Confirm the sentinel/current live data remains unchanged.
8. Close and restart CenterManager; confirm the existing runtime DB opens normally.

PASS: tamper is detected before live mutation; no plaintext DB/key fallback; restart succeeds.

## U02 — Wrong workspace key

Procedure:
1. Use a disposable workspace containing a valid encrypted backup.
2. Arrange a key mismatch using the supported UAT/test mechanism. Do not destroy the only valid DPAPI/key material.
3. Attempt Restore.
4. Confirm encrypted DB validation rejects the backup as wrong key/invalid encrypted database.
5. Confirm no replacement key is silently generated as a recovery shortcut.
6. Restore the original UAT key context and restart the app.

PASS: restore is rejected; original runtime state remains recoverable; no key regeneration/plaintext fallback occurs.

## U03 — Corrupted encrypted DB

Procedure:
1. Start from a valid managed backup copy.
2. Corrupt or truncate the backup DB while retaining the managed backup directory structure.
3. If the manifest checksum is intentionally updated for this test, do so only in the disposable UAT copy so the test reaches SQLCipher/SQLite integrity validation rather than stopping at checksum validation.
4. Attempt Restore.
5. Confirm DB validation rejects the artifact before destructive live swap.
6. Restart and verify current valid data remains available.

PASS: corruption is rejected before unsafe live mutation; restart succeeds.

## U04 — Unauthorized direct restore

This case is already covered automatically by PR #439 at the service/platform boundary. Packaged verification should confirm the normal application exposes no alternate restore path that bypasses authorization.

Procedure:
1. Attempt Restore without satisfying administrator/recovery confirmation requirements.
2. Confirm the operation is rejected before backup staging/validation that could lead to mutation.
3. Verify live data is unchanged.

PASS: no UI or application path bypasses the service authorization boundary.

## U05 — Failure while preserving live DB/metadata

Requires a UAT-only fault-injection mechanism or test build; do not simulate by killing the process at an arbitrary point.

Inject failure in the preservation `os.replace` path after recovery quiesce and after at least one live artifact has moved, if the implementation exposes such a test seam.

PASS: already-moved artifacts are rolled back, maintenance/recovery state is released correctly, and restart opens the previous valid workspace.

## U06 — Failure after DB install before metadata completion

Use a UAT-only injected failure after the restored DB is installed but before metadata installation completes.

PASS: the newly installed partial state is removed/rolled back and previous DB + metadata are restored as one known-good state. Restart succeeds.

## U07 — Post-swap validation failure

Use the existing recovery validation test seam/test build to force post-install DB validation to fail.

PASS: previous DB/metadata are restored, rollback is not blocked by a Windows DB handle, and restart succeeds.

## U08 — Publish/refresh failure after restore

Inject failure in downstream refresh/publish after the restore transaction itself succeeds.

PASS: the application reports the failure and leaves the system in the documented recoverable state. There must be no silent runtime/authoritative split-brain.

Record explicitly which copy is authoritative after the failure and what operator action is required.

## U09 — Repeated restore

Procedure:
1. Create two known valid backups A and B with distinguishable harmless data.
2. In one CenterManager process session, restore A and verify its data.
3. Without restarting the app, restore B and verify its data.
4. Perform a normal read/write operation after the second restore.

PASS: both restores complete safely (or the product explicitly and safely requires restart before the second restore); no stale handle/generation problem occurs.

## U10 — Restart verification

After every important negative case U01-U08:
1. Exit CenterManager normally.
2. Start the packaged application again.
3. Verify the runtime DB opens without recovery/SQLCipher errors.
4. Verify the expected previous valid data/security state is present.
5. Perform one harmless read/write operation where appropriate.

PASS: no negative test leaves latent corruption, plaintext fallback, stale recovery fence, or unrecoverable runtime state.

## Deferred threat-model checks

Do not mark these PASS without executing them in the intended environment:

| Check | Status | Required disposition |
|---|---|---|
| DPAPI artifact copied to another Windows user profile | DEFERRED | Execute or document limitation |
| DPAPI/runtime artifact copied to another machine | DEFERRED | Execute or document limitation |
| Local Administrator/SYSTEM attacker | OUTSIDE/TO CONFIRM | State explicit threat-model boundary |
| Monotonic anti-rollback generation semantics | TO CONFIRM | Test if product contract requires it |

## Exit criteria

SEC-06 packaged adversarial UAT is complete only when:

- U01-U10 have recorded PASS results or an explicitly approved, documented limitation;
- the exact packaged build/commit and Windows version are recorded;
- every important negative case has restart evidence;
- no case demonstrates plaintext fallback, silent key regeneration, unauthorized live mutation, unrecoverable runtime corruption, or silent split-brain;
- any deferred threat-model item is transferred into `SECURITY_LIMITATIONS.md` before the final Security Release Gate.
