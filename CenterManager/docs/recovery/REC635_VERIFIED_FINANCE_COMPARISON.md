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

**Critical:** The newer Git MAIN-first review-notice path introduced by PR
#633 retains the old database/WAL under `startup-rollbacks`, whereas this
increment supports only legacy **verified RV-03 captured Recovery Cases**.
A startup rollback copy has not been proven to be a WAL-complete authenticated,
standalone SQLCipher snapshot, and the review notice does not cryptographically
pin its folder. Therefore this increment deliberately does **not** read that
copy, guess the correct folder or auto-create an apparent verified capture.
A separate, crash-safe capture provenance design and Windows migration tests
are required before supporting modern review notices.

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
