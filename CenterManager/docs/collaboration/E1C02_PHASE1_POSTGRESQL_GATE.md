# E1C-02 Phase 1 — PostgreSQL authority hardening

Status: **CODE COMMITTED, STAGING INTEGRATION NOT VERIFIED**.

## Changes

- Coordinator command compares lease expiry against **PostgreSQL primary clock_timestamp()**, not the Windows/Python process clock. SQLite's own clock is used for isolated unit-test-only mode.
- Authority row is acquired with `SELECT ... FOR UPDATE` inside the same transaction that records authority revision, idempotency receipt, audit row and optional publication outbox. READ COMMITTED PostgreSQL serializes contenders for the same repository row.
- Added `coordinator/migrations/001_initial_postgresql.sql` baseline schema (staging empty DB only, constraints + foreign keys).
- Added isolated PostgreSQL integration tests with two separate connections/threads: simultaneous acquire, publish/revoke race and server-clock enforcement. The suite skips explicitly if no staging URL is supplied.

## Mandatory execution

1. Provision a **disposable PostgreSQL** database with no production data/credentials.
2. Use dedicated role allowed to create/drop **test-only schemas**, set `E1C_TEST_POSTGRES_URL`.
3. Run `python -m pytest tests/test_e1c02_postgres_concurrency.py -vv -ra` from CenterManager.
4. Require **3 PASS and 0 SKIP** in this PostgreSQL integration run; full Windows CI passing while these 3 tests are skipped does **not** meet Phase 1 gate.
5. Repeat with multiple independent processes as part of the subsequent stress suite; this first gate uses separate PostgreSQL transactions and connections inside one Python process.
6. Capture server PostgreSQL version, test SHA and test DB URI with credentials redacted.

## Remaining hardening required before production

- DB-side `clock_timestamp()` use requires primary DB connection; forbid read-replica authorization decisions.
- Coordinator bootstrap is a staging helper; production migrations and initial authority insertion require explicit access policy and controlled operator execution.
- Enforce PostgreSQL-only deployment configuration; SQLite is never a multi-instance authority engine.
- Lease expiry, queue, request idempotency and race paths need crash/partition/load tests; no production release until independently verified.
- No Windows integration, token cutover, remote Git authorization change or data migration occurred.
