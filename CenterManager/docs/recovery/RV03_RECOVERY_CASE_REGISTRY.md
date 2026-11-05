# RV-03 — Recovery Case Registry and safe MAIN startup

**Issue #595 · PR #600 · Draft implementation pending Windows CI and packaged EXE UAT.**

## Current design

Reuse the existing WriteRecoveryJournal.reconcile(), preserve(), verify_capture(), and StartupSynchronization preflight. The RV-03 registry is not a separate recovery engine and does not merge, replay or publish data.

1. Startup verifies fetched and independently observed Git MAIN OIDs, with local WRITE authority closed.
2. Existing reconciliation makes an authenticated WAL-consistent backup of SQLCipher DB, attachments and assets, and verifies the immutable capture.
3. Before Git reset, RecoveryCaseRegistry creates a signed case under the sibling .write-recovery/cases directory, tied to the capture digest, repository and base MAIN.
4. Only then does the existing startup process proceed to pinned Git reset and atomic SQLCipher install. The previously implemented interrupted-install rollback/replay remains authoritative.
5. If startup is interrupted after reconciliation but before case persistence, the next run reconstructs the case from the verified capture; an invalid, missing or tampered case blocks continuation.

## Recorded evidence

| Field | Meaning |
| --- | --- |
| case_id | Deterministic incident identity from repository, base OID, session ID or legacy capture hash |
| status | PENDING_REVIEW until explicit future acknowledgement |
| write_session_id and base_main_oid | Original edit provenance |
| observed_main_oid | Remote MAIN observed during the reconciliation |
| publication and published_oid | VERIFIED only with matching journal proof; otherwise UNVERIFIED, never assumed missing |
| capture_ref and capture_db_sha256 | Verified immutable snapshot reference and DB fingerprint |
| change_log_coverage | UNKNOWN until a separate authenticated outbox/mirror comparison proves coverage |

Production case metadata is authenticated using the existing protected SQLCipher key; a missing key blocks. Nonproduction plaintext tests use a SHA-256 integrity marker, which is not cryptographic authentication.

## Safety and exclusions

- Git MAIN remains authoritative. No automatic database merge/replay, remote push, lock TTL/grace change, force-release or new WRITE authority.
- A Recovery Case only blocks unsafe replacement; the existing journal, mutation gate, remote OID checks and install fences decide whether replacement is authorized.
- Backups and cases survive subsequent startup and Finish Editing; failed or UNKNOWN publication never means edits are proven absent from MAIN.
- No raw student notes, salary/finance details, passwords, credentials, key bytes or remote URLs in case metadata.
- RV-04 will provide privileged case review and acknowledgement; no UI exposure or acknowledgement is added by this PR.

## Tests and remaining release gates

Included synthetic tests: unique case per incident, restart persistence, missing/tampered capture, case HMAC tampering, distinction of verified/unknown publish, fail-closed startup on case-disk failure and retry without duplicates.

Outstanding: latest Windows CI on PR #600; real encrypted SQLCipher/WAL Git A→A+10 two-machine test; interrupted-install process kill; stale writer/publisher fencing; old EXE missing outbox; attachments and Windows DPAPI access; packaging/UX UAT. Do not merge PR #600 or close #595 before those gates pass.

## Phase 2 — durable case lifecycle hardening

The registry now persists a case anchor in the existing recovery journal as `rv03_case_id`, **after** an authenticated case file has been fsynced. A crash between case persistence and journal pinning is recoverable: a subsequent RECONCILED startup verifies the same capture, finds the immutable case and pins it without creating another. During later normal CLEAN startups with an RV-03 pin, the preflight authenticates the case and revalidates its original captured DB fingerprint. A missing, tampered, or missing-key case blocks startup; legacy CLEAN journals without a pin use the original fast path. There is no auto-acknowledgement.

All case creation retains `change_log_coverage=UNKNOWN` and distinguishable `publication=VERIFIED|UNVERIFIED`. A verified publication is not a claim that all later local mutations reached MAIN.

## Phase 3 — safe MAIN A→A+10 integration coverage

Added an isolated encrypted SQLCipher + actual local Git remote test in `test_e1b1_durable_write_recovery.py`:
- Client A begins editing from base commit A and commits `LOCAL_UNACCEPTED` to its encrypted runtime.
- A separate repository clone pushes ten legitimate remote commits without the local edit; MAIN advances to A+10.
- Startup fetches independently observed A+10, reconciles the local workspace, verifies WAL-complete encrypted snapshot and persists PENDING_REVIEW case **before** resetting Git and installing MAIN.
- Assert the new runtime matches MAIN (BASE only), the exact old capture still contains LOCAL_UNACCEPTED, and no local edit was published/merged.
- Re-run startup; assert the case is still PENDING_REVIEW and no duplicate case appears.

Additional regression: when remote MAIN changes after a previous RECONCILED capture approved another OID, **fail closed rather than installing a newer OID using stale proof**. Existing startup rollback/replay and E1B guards are reused unchanged.

## Deferred gates

Synthetic and isolated Git/SQLCipher integration tests are not packaged EXE UAT. Before production merge, still require 2-machine stale WRITE owner and old EXE testing, Windows process-kill during recovery/atomic install, DPAPI same-user recovery and inaccessible-key behavior, large attachments verification, and final code review. The remote lock TTL/grace, MAIN CAS and force-release behavior must remain unchanged.
