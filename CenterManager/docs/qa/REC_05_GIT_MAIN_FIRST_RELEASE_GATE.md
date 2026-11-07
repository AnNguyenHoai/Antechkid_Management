# REC-05 — Git MAIN First / Non-blocking Recovery acceptance gate

## Decision

Git MAIN is authoritative; local recovery is retained for manual review only. A historic incident must not block READ/WRITE on a **new, independently accepted** MAIN workspace. It must also never be silently published, merged, deleted or treated as CLEAN by changing JSON status.

## Implemented in this PR stack

- REC-01: null/missing legacy capture journal compatibility; invalid/mismatched evidence still refused.
- REC-02 foundation: stage a freshly verified exact MAIN database/identity/manifest separately; never mutate a user DB/WAL/recovery during stage. Not yet connected to production activation.
- REC-03 foundation: proof of independently accepted MAIN generation, without using historic case status to prove a new active generation. Does not itself grant WRITE.
- REC-04: nonmodal reminder menu and status bar; manual case review retains explicit acknowledgement.
- REC-05: deterministic fault injection for remote MAIN advance during staging, IO errors, identity validation rejection, and tampered receipts.

## HARD RELEASE BLOCKERS — not yet implemented / verified

- [ ] Crash-safe activation of staged MAIN into a new active workspace, without overwriting any legacy local database, WAL, attachments, journal, or original recovery capture; migration/repository identity and windows path scoping must be addressed
- [ ] Signed durable record of archived incident/reference that survives process crashes while workspace routing changes
- [ ] Fresh active WRITE receipt created from the actual accepted and migrated MAIN bytes; **no** reclassification of historic OPEN/PUBLISHING evidence as CLEAN
- [ ] Only current active workspace's accepted-main provenance participates in Start Editing; remote lease, fencing and publish CAS still enforce WRITE
- [ ] Recovery UI can list archived old incidents even if stored outside the active workspace, without granting WRITE or silently acknowledging any record
- [ ] Multi-process and legacy executable publisher tests; no stale client can publish previous local state
- [ ] Two-machine Windows EXE UAT and fresh-install/upgrade/rollback compatibility
- [ ] Latest Windows CI green on all five PR heads after the final commits

Never mark REC-02 and REC-03 complete or merge their foundations as finished nonblocking startup. Having a stage/receipt alone does not mean the active runtime has switched.

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
