# E1C-02 Phase 4 — Windows Adapter & Deployment Preparation

**Status:** Opt-in transport and protocol boundary implemented; NOT attached to production WRITE workflow; production cutover **BLOCKED**.

## Confirmed existing incompatibility

Current `WriteTransactionManager._publish()` invokes `WriteRecoveryJournal.published(provider)`, which requires **Git local/remote MAIN OID equality** and a hash-consistent repository snapshot. E1C coordinator acceptance instead has a durable server **receipt**, and Git MAIN is merely an asynchronously updated projection. Replacing `SynchronizationManager.publish_only` directly while leaving this journal check unchanged could incorrectly mark accepted publications failed, or mistakenly clean unaccepted data.

The present `WriteTransactionManager._release_lock()` also depends on Git-based collaboration ownership/release. A safe coordinator integration must migrate acquisition/renew/release and publish/journal verification **together**. A transport adapter alone must never be activated in that workflow.

## Implemented in this phase

- `coordinator/client_adapter.py`: explicit HTTPS-only, caller-supplied token provider, protocol label `e1c/1`, typed error codes; no direct Git fallback.
- `CoordinatorProtocolGate`: disabled by default; refuses unsupported protocol and explicit legacy Git publication fallback.
- `publish_candidate()`: sends a single publish command, then queries the exact server `request_id` receipt and compares intended ciphertext hash. Lost HTTP ACK => read-only reconciliation, never second blind POST. Unknown/mismatched receipt => fail closed.
- `test_e1c02_client_adapter.py`: HTTPS, disabled gate, unsupported version, lost-ACK, mismatched receipt and no blind retry.
- No imports into Windows UI/startup/runtime. No credential or data Git setting change. No production deployment.

## Required implementation before any live Windows integration

1. Introduce `CoordinatorWriteSession` backed by server acquisition, renewal, release and version negotiation; it must never interpret local Git owner state as coordinator authority.
2. Add coordinator-native recovery journal receipt fields (`request_id`, `candidate_sha`, `accepted_revision`, `epoch`, `signed_receipt`) and independent verification of local SQLCipher fingerprint; preserve E1B-1 recovery journal schema migration and existing Git records. Do **not** call legacy `published(provider)` on coordinator path.
3. Replace startup sync accepted snapshot adoption with coordinator-authoritative candidate pointer/receipt plus verified signed identity; never trust projected MAIN without receipt match.
4. Add atomic feature/version cutover state: coordinator-only writers, legacy EXE blocked from WRITE; app startup should fail READ-only when coordinator unavailable.
5. Implement real OIDC/JWT authentication, TLS pin/validation policy, secret/credential lifecycle and admin step-up.
6. Server candidate validation must include trusted SQLCipher integrity/provenance before acceptance. Current Phase 2 signature+hash is not enough.
7. Git projector must emit full database + signed identity/manifest, persist projected OID and support existing repository bootstrap.
8. Use an isolated staging remote and PostgreSQL primary to test 2 independent Windows EXEs including crash / WAL / lost ACK / stale lease / stale legacy push.
9. Production direct-push credential removal, protected-ref verification, rollback and hosting infrastructure require separate founder approval.

## Deployment / rollback preparation

- Three independent environments: local disposable Git/SQLite tests; PostgreSQL isolated staging; production with approved hosting and backups.
- Staging protocol can be rolled back to **READ-only** without recreating old Git MAIN push permissions.
- On unknown publication receipt, preserve SQLCipher database, WAL and journal snapshots; never delete recovery evidence.
- Release gates: actual PostgreSQL contention tests 0 SKIP, fail-closed legacy EXE denial on production-equivalent remote, valid receipt-vs-snapshot integrity, multi-PC end-to-end, signer key custody and backup recovery.
- **Do not merge PR #537 as production-ready** on Windows CI success alone.
