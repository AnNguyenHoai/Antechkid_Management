# E1C-02 implementation PR — scope, evidence and release gates

## Status: STAGING SCAFFOLD / NOT DEPLOYABLE TO PRODUCTION

This single implementation PR adds isolated coordinator modules. No Windows runtime wiring, existing WRITE lock, Git synchronization, SQLCipher key path, credentials, database or Git production settings are changed.

### Included

- `coordinator/authority.py`: SQLAlchemy transactional owner epoch/revision, lease acquire/renew/release/revoke, immutable request receipts, candidate registration, accepted pointer and projection outbox.
- `coordinator/storage.py`: local content-addressed byte storage for **disposable staging only**; never stores SQLCipher key.
- `coordinator/api.py`: optional FastAPI router requiring injected independently authenticated principal verifier; no default unsafe token fallback.
- Tests: deterministic single-process SQLite state and data integrity assertions.
- Optional dependency list separate from Windows requirements.

### Security constraints

1. **This is not yet a functional server-side production fencing solution.** API registration currently marks uploaded candidates `verified=False` and therefore intentionally prevents any candidate from being accepted without a future trusted manifest/signature and SQLCipher artifact validation path.
2. Git MAIN projection worker is **not implemented**. Outbox is persisted but not consumed; no actual Git write occurs.
3. Candidate repository identity / trusted signature, object-store durable upload, OIDC/JWT token verification, admin step-up, queue FIFO, database schema migrations, monitoring and backup/recovery remain NOT IMPLEMENTED.
4. The API accepts caller session identifiers through an authenticated application identity but an external caller-supplied `admin_authorized` flag is explicitly discarded.
5. PostgreSQL `SELECT FOR UPDATE` is the required multi-instance serialization primitive. SQLite is **test-only**, not a production concurrency guarantee.
6. `create_schema_for_tests` and `bootstrap` are test/bootstrap helpers; no implicit production provisioning permitted.
7. No legacy EXE direct-push credential has been revoked; **P0 remote publication bypass remains NOT VERIFIED**.
8. These tests do not prove 2-Windows-client, GitHub production branch protection, live revocation, key custody or failover.

### Before staging integration / production (blocking tasks)

- Implement signed manifest identity verification and trusted candidate readiness; prevent arbitrary admin `verified=True` paths from public API.
- Implement real S3/R2 durable storage with no snapshot accepted before durable object upload confirmation.
- Implement IdP OIDC verification, repository authorization, client version and permission checks, admin second factor.
- Implement PostgreSQL schema migration, DB-time lease checks, row-level transaction isolation integration tests, concurrency with independent workers/processes; avoid relying on app clock.
- Implement projection worker from outbox with idempotent exact Git OID checks and checksum validation; projection errors must never mean acceptance failure.
- Migrate Windows `publish_only`, startup sync and recovery journal to verified coordinator receipts behind explicit protocol/version gate, while blocking legacy write paths.
- Rotate/revoke old desktop push credentials and enforce Git MAIN permissions on the **actual data repository**.
- Add crash, ambiguous ACK, recovery and stale EXE push denial tests in production-equivalent staging.
- Demonstrate production rollback is READ-only and never re-grants retired MAIN push permissions.

### Recommended review sequencing inside this single PR

Review code boundaries and test results separately; merging code to source does not imply activation. Keep PR Draft until isolated CI passes. Even a green CI does NOT permit production switch. Separate explicit approval for hosting, key custody, credentials and deployment is mandatory.
