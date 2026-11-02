# E1C-02 Phase 2 — Candidate Verification & Security (staging)

**Status:** Implemented minimal signed-candidate validation boundary; **NOT PRODUCTION READY**.

## Source changes
- `coordinator/verification.py` validates strict, canonical JSON manifests and pinned per-repository Ed25519 signing keys, repository ID, database ID, positive generation, ciphertext SHA-256 and exact storage byte size.
- `coordinator/storage.py` checks immutable content-addressed staging bytes and provides authenticated byte size (local staging only, not durable multi-server object storage).
- `coordinator/api.py` distinguishes **UPLOADED_UNVERIFIED** from trusted verification. New authenticated `POST /v1/repositories/{repository}/candidates/verify` requires configured `CandidateVerifier`, a pinned trust root and a valid detached signature. The upload API does **not** mark candidates verified.
- `test_e1c02_candidate_verification.py` covers valid signed candidate acceptance, tampering, signature mismatch, wrong repository/database identity, wrong size/hash, replayed generation and unverified candidate rejection.

## Security invariant

Untrusted uploads cannot directly set the `Candidate.verified` database flag using the HTTP API. Verification requires a trusted **server-configured** Ed25519 public key (not a key provided by an uploader), manifest identity and matching immutable bytes. Publication continues to enforce current owner, epoch, revision and generation.

A valid manifest signature proves that the trusted signing key signed exactly the declared manifest. **It does not alone prove SQLCipher decryptability, foreign-key validity, business integrity, student financial invariants or freshness if the signer is compromised.** Signed manifests cannot replace SQLCipher integrity checks at a separately trusted validation boundary.

## Important remaining P0 gates

1. **Signer key custody and provisioning:** create server-managed trust-key registration, rotation and revocation with audit; never trust client-supplied public keys. A compromised signer can sign harmful ciphertext.
2. **Trusted SQLCipher verification:** choose approved mechanism for validating encrypted snapshot consistency without exposing sensitive key material to an untrusted coordinator. Until proven, no production acceptance.
3. **Durable object storage:** staging local filesystem must be replaced with S3/R2-compatible durable uploads; verify object durability and metadata before setting verified state. Include immutability, retention, and storage IAM.
4. **Authentication:** current `build_app` still requires injected token verifier, not a production OIDC/JWT implementation; scope and user identity verification remain outstanding.
5. **API abuse prevention:** replace hex-in-JSON uploads with bounded streaming/presigned uploads, TLS, authenticated size limits and request throttling; ensure verification cannot be used for CPU/disk exhaustion.
6. **Race-free verification:** signed manifest provenance, verified metadata and ciphertext digest should be bound in persistence and rechecked under publish; current schema has only `verified` plus hash/identity/generation (no signature provenance/audit).
7. **External consistency:** PostgreSQL concurrency gate from Phase 1 still requires real isolated PostgreSQL execution; Windows CI PASS with skipped integration tests does not satisfy it.
8. **Remote fencing:** direct legacy Git push permissions have not been disabled; Git projection worker and Windows transport adapter are absent.

## Release verdict

**Phase 2 staging implementation: implemented, pending CI. Production acceptance: BLOCKED.** No production Git, token, database, release environment or Windows client integration changed.
