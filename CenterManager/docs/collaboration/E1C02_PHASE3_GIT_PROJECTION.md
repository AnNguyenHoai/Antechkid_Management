# E1C-02 Phase 3 — Git Projection & Durable Outbox

Status: **staging implementation committed; NOT PRODUCTION READY**.

## What is implemented

- `coordinator/projector.py`: isolated Git worker reads unprojected outbox events in revision order under repository authority row lock, verifies candidate hash against staging blob store, creates Git commit containing encrypted `database/center.db` and `e1c-projection.txt`, and pushes to staging MAIN using exact expected remote ref OID.
- On uncertain push ACK, the worker re-reads remote MAIN. It marks projected only when the intended OID is observed. A retry after a crash can reconcile an already-accepted event by matching exact candidate hash/revision in the remote projection marker without creating a duplicate commit.
- Unexpected remote commits without the coordinator marker, and out-of-order revision markers, fail closed.
- Accepted PostgreSQL authority state and receipt are NEVER undone when Git projection fails. The outbox remains pending for explicit recovery.
- Tests: disposable bare Git remote, successful ordered projection, after-push crash/lost acknowledgement with exact reconciliation, and foreign remote history conflict.

## Important limitations / release blockers

1. Git remote permissions are NOT changed. A malicious legacy credential able to update MAIN can still bypass server-side fencing; QA-P0-02 must demonstrate credential cutover and remote denial. The marker is an integrity/reconciliation aid, **not** an authorization mechanism.
2. This worker is for **isolated staging only**. Its local-file Git remote and local object store are not durable production hosting.
3. The projector currently writes ciphertext and a projection marker only. It does not yet project the authoritative signed SQLCipher identity sidecar, manifest or validated compatibility artifact set. Do NOT configure Windows startup sync to consume its output.
4. Worker uses synchronous Git subprocess under a DB lock; requires timeouts, worker lease discipline, retry scheduling, monitoring and stricter concurrency/poison-event controls before production.
5. Projected receipt/OID is not yet persisted in the outbox or authority metadata; production must persist both receipt and remote OID for audit/reconciliation.
6. Bootstrap from a preexisting authoritative Git repo requires a signed/matched import and cutover procedure. This worker deliberately denies a foreign/unmarked remote.
7. Current candidate signing proves only signed manifest integrity, not SQLCipher decryptability/foreign keys and actual business consistency. Trusted validation remains P0 outstanding.
8. PostgreSQL concurrency integration tests and real multi-client/legacy Windows UAT remain separately gated and must not be counted as PASS merely from standard Windows pytest.
9. No change to Windows EXE publication, runtime recovery journal, Git production remote, credentials or branch protection.

## How to validate

From CenterManager directory, run:
`python -m pytest tests/test_e1c02_git_projector.py -vv -ra`

Then run full Windows three-shard CI on exact PR HEAD. Keep PR Draft until independent security and production integration gates are verified.

## Next phase

Phase 4: separate coordinator client adapter, protocol negotiation, immutable accepted-snapshot read path, E1B durable journal and explicit fail-closed downgrade protection. The cutover of old Git credentials is a separate founder-authorized operation.
