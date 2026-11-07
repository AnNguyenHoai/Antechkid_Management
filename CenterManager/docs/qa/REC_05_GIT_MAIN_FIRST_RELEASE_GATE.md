# REC-05 — Git MAIN First / Non-blocking Recovery acceptance gate

## Decision

Git MAIN is authoritative; local recovery is retained for manual review only. A historic incident must not block READ/WRITE on a **new, independently accepted** MAIN workspace. It must also never be silently published, merged, deleted or treated as CLEAN by changing JSON status.

## Implemented in this PR stack

- REC-01: null/missing legacy capture journal compatibility; invalid/mismatched evidence still refused.
- REC-02: stage independently verified exact MAIN artifacts and prepare a separate candidate runtime containing only the current user's protected workstation configuration, never copying old DB/WAL/Recovery.
- REC-03: on recovery-specific bootstrap failure, attempt an independent Git MAIN bootstrap into the candidate runtime; after normal SQLCipher/schema and recovery receipt acceptance, atomically route future launches to this new active runtime. The old workspace and journal remain at their original paths. Existing WRITE lease, fencing and publication CAS remain authoritative.
- REC-04: nonmodal reminder menu and status bar; retained historic case registries can be viewed at original untouched roots; manual acknowledgement remains explicit.
- REC-05: deterministic fault injection for remote MAIN advance during staging, IO errors, identity validation rejection, and tampered receipts.

## HARD RELEASE BLOCKERS — not yet implemented / verified

- [ ] Complete fault-injection of new-runtime boot + atomic active-pointer transition under kill/process crash, Windows file-lock contention, schema migration and EXE upgrade; code paths exist but have not undergone physical UAT
- [ ] Formal security review of the active-runtime pointer and retained-root registry, including cross-process CAS, Windows ACLs, symlinks, DPAPI key portability and release-folder upgrades
- [ ] Confirm fresh active WRITE receipt is created from accepted migrated MAIN bytes and no historic OPEN/PUBLISHING evidence is reclassified as CLEAN across real Windows EXE restarts
- [ ] Validate two-machine WRITE lease/fencing/CAS and ensure no older client publishes an archived runtime following pointer migration
- [ ] Windows UAT of archived Recovery Case review UI (including malformed/legacy case), with no acknowledgement or auto-publish
- [ ] Multi-process and legacy executable publisher tests; no stale client can publish previous local state
- [ ] Two-machine Windows EXE UAT and fresh-install/upgrade/rollback compatibility
- [ ] Latest Windows CI green on all five PR heads after the final commits

Do not merge/ship any REC-02/03/04/05 implementation before fresh MAIN startup, old workspace retention, replay/routing and two-machine Windows UAT are signed off. A passing test of staged bytes alone does not authorize WRITE.

## Windows UAT matrix

1. Authoritative MAIN stable and old local journal CLEAN → open normally, READ, acquire lease, edit and publish, observe from second machine.
2. Old local journal OPEN, PUBLISHING, POST_PUBLISH_PENDING, RECONCILED, missing/corrupt JSON or absent signed Case → archive/isolate the original without mutation; open a NEW MAIN workspace; show review indicator; do not replay old local into MAIN.
3. Simulate power loss after archive reservation; after one copy; after durable journal/capture; after staging DB; after commit-OID proof; after active switch. Every restart should either finish cleanly or safely fall back to prior untouched evidence.
4. Loss of Git, revoked token, missing Git binary → verified cached READ only; WRITE denied until MAIN and lease verified.
5. Missing/wrong DPAPI key, SQLCipher authentication failure, identity generation downgrade → do not accept unverified DB or create a new key for old ciphertext.
6. Remote MAIN advances after fetch or while staging → abandon stale stage; retry without WRITE.
7. Runtime DB contains uncheckpointed WAL or raw DBAPI handle open → never truncate/reuse it while opening a new main-only workspace.
8. Recovery Case is missing/corrupt on the old workspace → show diagnostic and allow manual investigation after NEW workspace activation; no case is silently stamped valid.
9. Multiple Windows users / copied portable EXE → credentials remain user-bound; new main workspace uses correctly provisioned secret; no accidental cross-account publishing.
10. File in use, disk full, antivirus quarantine, insufficient permissions → no mutation of old database, attachments and recovery evidence; no partially accepted new workspace.
11. Recovery notification skipped/reopened/acknowledged → only explicit operator review changes signed case state.
12. Compare hashes and Git OID before/after every failure injection; assert no unintended Git push, DB mutation, or change-log replay.

### CI success is not sufficient

CI unit tests validate isolated components and established contracts. A full successful EXE + two-machine acceptance is mandatory before any production startup/WRITE activation.
