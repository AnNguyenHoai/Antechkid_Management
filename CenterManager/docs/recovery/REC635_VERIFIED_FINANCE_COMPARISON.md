# REC-635 — Verified SQLCipher finance comparison (increment 1)

## Implemented

On explicit post-login command from **Khôi phục > Danh sách Recovery Case**, the
operator with `finance.view` may export a JSON financial comparison. The process
does **not** run on startup, in a background thread, or on ordinary Save.

Strict read boundary:
1. Authenticate the Recovery Case and its immutable capture manifest via the
   existing `RecoveryCaseRegistry` and `WriteRecoveryJournal.verify_capture`.
2. Verify complete old DB checksum; obtain its original user-scoped DPAPI key
   from the preserved capture. No new keys are generated.
3. Verify fetched, current local and independently observed remote Git MAIN
   OIDs match **at comparison time**; fail if offline/stale.
4. Validate authoritative repository database and signed identity, and old
   SQLCipher artifact; refuse pending SQLite WAL/journal sidecars.
5. Open both artifacts through immutable read-only SQLCipher handles and enable
   `PRAGMA query_only`. Read only allowlisted finance columns.
6. Reverify manifest and MAIN DB/identity and remote OID afterward. Fail rather
   than returning a report if sources changed.
7. User explicitly selects local export file. Sensitive plaintext is never
   written automatically; report is written to an exclusive temp file and then
   atomically renamed. A privacy warning precedes the export.

### Supported tables and matching

- `incomes`, `expenses`, `tuition_adjustments`
- `monthly_tuition_outcomes`
- Identity: nonempty, unique, stable `idempotency_key` only.
  Integer auto-increment IDs are **not** an identity match; an ID collision with
  a different key produces `UNKNOWN`.
- Values: allowlisted money, dates, payment method, status and related IDs.
  Field diffs are returned without attempting any mutation or fix.
- `PRESENT_IDENTICAL` — matching stable key and all compared values.
- `PRESENT_DIFFERENT` — matching stable key with different compared values.
- `NOT_FOUND` — unique key absent in the currently authenticated MAIN snapshot
  and no conflicting ID reuse. **This is not proof of unpublished income.**
- `UNKNOWN` — null/duplicate key, ID reuse, missing schema or too many rows.

### Unresolved operational gaps (Issue #635 remains open)

**Modern Git MAIN-first review notices (PR #633):** This PR additionally
binds the old `startup-rollbacks` DB/WAL/SHM to the exact review notice with an
HMAC-authenticated per-file SHA-256 inventory on the *recovery-only* startup
path. This binding is best-effort; failure never blocks startup. Without its
proof, old bytes are deliberately not compared. On explicit operator request,
the old signed bytes are copied into an isolated temporary folder, SQLCipher
replays/checkpoints the detached WAL **only on the copy**, integrity is checked,
then the immutable copy is compared to independently verified remote MAIN.
The signed old bytes are re-checked after comparison; the report is discarded
if any authenticity or source-stability check fails.

**Remaining gate for modern path:** packaged Windows EXE tests (including crash
between old DB move and signed proof, DPAPI same/different user, WAL crash,
multi-GB startup performance, two-machine races). A malformed, missing or
corrupt proof is an UNKNOWN/UNAVAILABLE report, never an excuse to overwrite
or discard the old rollback.

Still missing: month plan default/activation/allocations, enrollment mapping
across DB generations, wallets and computed outstanding, current student
name lookup, old schema compatibility, attachment content checks, deep
permission/cross-user Windows UAT, actual packaged EXE/DPAPI tests and two
machine reproducibility. Old entries without idempotency keys stay UNKNOWN.
Also check whether raw finance UI permissions require additional restrictions
beyond `finance.view` in the deployment policy.

## Release gate

Do not label Issue #635 completed until a verified modern startup rollback
snapshot can be selected by an authenticated review notice and the real Windows
UAT gates pass. Git MAIN remains the source of truth. Never replay old records.
