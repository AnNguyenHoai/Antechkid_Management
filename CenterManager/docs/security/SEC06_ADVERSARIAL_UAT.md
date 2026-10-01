# SEC-06 Adversarial Backup & Recovery UAT

## Purpose

Phase 1 proved the Windows happy-path restore after the runtime DB ownership fixes. Phase 2 proves that hostile, corrupted, unauthorized, or interrupted restore inputs fail closed without silently weakening the encrypted production boundary.

## Global acceptance invariant

For every negative case below, the expected outcome is:

1. the attack/failure is detected;
2. restore does not proceed past the first unsafe boundary;
3. no plaintext fallback is created;
4. the workspace key is not regenerated as a recovery shortcut;
5. the live runtime database remains valid or is rolled back to a known-good copy;
6. the failure is surfaced to the caller/operator.

## Automated contract coverage

| ID | Scenario | Expected result | Coverage |
|---|---|---|---|
| A01 | Direct platform restore without authorization | Reject before backup validation/staging | Automated |
| A02 | Forged `RestoreAuthorization` dataclass | Reject; private authority token cannot be forged | Automated |
| A03 | Non-admin requests restore authority | Reject | Automated |
| A04 | Empty reason or confirmation | Reject | Automated |
| A05 | Backup path outside managed backup root | Reject before DB validation | Automated |
| A06 | Encrypted backup bytes tampered after manifest creation | Reject checksum mismatch | Automated |
| A07 | Wrong workspace key / invalid ciphertext | Reject encrypted DB validation | Automated contract + packaged UAT |
| A08 | Plaintext/legacy backup while encryption is required | Reject | Automated |
| A09 | Metadata half missing | Reject before live mutation | Automated |
| A10 | Backup format newer than supported application | Reject fail-closed | Automated |

Automated tests live in `tests/test_sec06_adversarial_restore.py`.

## Manual / packaged Windows adversarial UAT

These cases must run against the packaged Windows application because they depend on DPAPI, SQLCipher/native file ownership, process restart, or injected destructive-operation failures.

| ID | Scenario | Procedure | PASS criteria |
|---|---|---|---|
| U01 | Tampered encrypted backup | Create backup; alter one byte of `center.db`; Restore | Restore rejected; current live data unchanged; restart succeeds |
| U02 | Wrong workspace key | Use a test workspace/key mismatch without replacing the valid key | Restore rejected as wrong key/invalid encrypted DB; no new key generated |
| U03 | Corrupted encrypted DB | Corrupt/truncate backup DB while retaining managed backup structure | Validation rejects before live DB preservation/swap |
| U04 | Unauthorized direct restore | Invoke application/service path without validated recovery authority | Reject; no staging or live mutation |
| U05 | Failure while preserving live DB/metadata | Inject an `os.replace` failure after quiesce | Rollback restores every already-moved live artifact; app restart succeeds |
| U06 | Failure after new DB install but before metadata completion | Inject failure at metadata install | New DB is removed; previous DB/metadata restored; restart succeeds |
| U07 | Post-swap DB validation failure | Force validation failure after installation | Previous DB/metadata restored; no Windows handle lock blocks rollback |
| U08 | Publish/refresh failure after restore | Inject downstream refresh/publish failure | System reports failure and remains in a documented recoverable state; no silent split-brain |
| U09 | Repeated restore | Perform two valid restores sequentially in one app session | Both complete or second is safely rejected; no stale handle/generation issue |
| U10 | Restart after every important negative case | Close/reopen packaged app | Runtime DB opens normally and previous valid data/security state remains intact |

## Deferred / threat-model dependent checks

The following must not be silently marked PASS. Either execute them in the intended deployment environment or record them in `SECURITY_LIMITATIONS.md` with rationale:

- DPAPI behavior across a different Windows user profile;
- DPAPI behavior after copying runtime artifacts to a different machine;
- attacker with local Administrator/SYSTEM privileges;
- rollback/anti-rollback semantics if the product contract requires monotonic authoritative generations.

## Evidence to retain

For each packaged UAT case retain: application build/commit SHA, Windows version, test ID, result, relevant log excerpt/error message, and a short verification that the live DB could be reopened after the case. Do not attach workspace keys, credentials, tokens, or decrypted database contents.

## Phase-2 exit criteria

Phase 2 is complete when all automated tests are green, U01-U10 have recorded PASS results (or an explicitly approved limitation where applicable), and no negative test can mutate the live database before authorization + validation + recovery quiesce boundaries are satisfied.
