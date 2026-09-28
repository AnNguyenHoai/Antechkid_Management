# SEC-06 — Real Windows Production Security UAT

## Purpose

Prove the merged SEC-01..SEC-05 security invariants on a real Windows production-like deployment. This is an acceptance/evidence gate, not a replacement for pytest.

Run only in an isolated UAT workspace with disposable data and a disposable private production-data repository. Never tamper with a live center database.

## Preconditions

- Windows 10/11 host using the same architecture as release machines.
- Current `main_repos` packaged/frozen build or source run with `ANTECHKIDS_DEPLOYMENT_PROFILE=production` for diagnostics.
- SQLCipher runtime packaged successfully.
- Fresh UAT workspace initialized with `scripts/initialize_production_database.py`.
- SEC-05 identity sidecar created through the controlled publication path before normal startup.
- Test Admin account and collaboration WRITE ownership available.

## Automated evidence probe

From `CenterManager`:

```powershell
python scripts/run_sec06_windows_production_uat.py --json artifacts/sec06/security-uat.json
```

Exit codes:

- `0`: every represented check passed and no manual check remains.
- `1`: at least one automated check failed.
- `2`: automated checks passed but real-machine/manual acceptance checks remain.

The harness never prints raw SQLCipher key material.

## Acceptance matrix

| ID | Acceptance criterion | Expected result |
|---|---|---|
| SEC06-01 | Real Windows host | PASS |
| SEC06-02 | Production runtime DB exists | PASS |
| SEC06-03 | DPAPI key bundle exists | PASS |
| SEC06-04 | DB header is not plaintext SQLite | PASS |
| SEC06-05 | Current Windows profile can unseal DPAPI key | PASS |
| SEC06-06 | SQLCipher artifact validation succeeds | PASS |
| SEC06-07 | Signed SEC-05 identity sidecar exists | PASS |
| SEC06-08 | Identity/hash/generation validates and pins | PASS |
| SEC06-09 | Fresh default Admin must change password | PASS |
| SEC06-10 | Missing/wrong local key fails closed; no replacement key appears | PASS |
| SEC06-11 | DB copied to unprovisioned Windows profile/machine cannot start | PASS |
| SEC06-12 | Backup is ciphertext; plaintext/wrong-key restore is rejected | PASS |
| SEC06-13 | Authorized encrypted restore succeeds | PASS |
| SEC06-14 | One-byte DB tamper is rejected | PASS |
| SEC06-15 | Older signed generation is rejected after newer generation was pinned | PASS |
| SEC06-16 | Normal Git publish/pull preserves database ID and advances generation | PASS |
| SEC06-17 | Injected publication/restore failure leaves no split artifact state | PASS |

## Manual execution notes

### SEC06-09 — first-login password change

Use a freshly initialized UAT database. Launch the packaged application, sign in with the seeded Admin credentials and verify that normal application access is blocked until the password-change flow succeeds. Retain a screenshot or sanitized application log; never record the password.

### SEC06-10 — missing key fail-closed

Close CenterManager. Move the UAT key bundle to a temporary safe location outside its configured path. Launch the packaged build. Startup must fail without creating a new workspace key or replacing the DB. Restore the original key bundle before continuing.

### SEC06-11 — DPAPI/profile boundary

Copy only the encrypted UAT DB and signed identity sidecar to a clean Windows profile or second UAT machine. Do not copy/provision the key. Startup must fail closed. This proves ciphertext portability does not imply key portability.

### SEC06-12/13 — backup and restore

Create recognizable disposable marker data and an encrypted backup. Confirm its first bytes are not `SQLite format 3`. Verify an invalid/plaintext restore is rejected. Then perform an authorized restore using Admin + WRITE + reason + exact typed confirmation and verify the marker state returns to the backup state.

### SEC06-14 — tamper

Work on a disposable copy of the DB+identity pair. Flip one byte in the DB without changing the sidecar. Startup/preflight must reject the pair because the SHA-256 no longer matches the signed identity.

### SEC06-15 — rollback

Retain generation N and N+1 of the same UAT database. Let the workstation validate/pin N+1, then substitute the signed N pair. Startup/preflight must reject it as older than the locally trusted generation. Do not delete the local identity pin between these steps.

### SEC06-16 — publication lifecycle

Record `database_id` and generation, make one disposable application change, publish through the normal production path, then pull/materialize normally. The database ID must remain stable and generation must increase monotonically.

### SEC06-17 — atomic failure safety

The deterministic fault-injection regressions are the preferred evidence for this destructive edge. If a real-machine fault test is performed, use only disposable UAT artifacts. After failure, validate DB, identity, metadata and WAL/SHM consistency and ensure no orphan `.previous-*` publication artifacts remain.

## Evidence package

Store sanitized evidence under a non-production artifact directory, for example:

```text
artifacts/sec06/
  security-uat.json
  environment.txt
  packaged-startup.log
  backup-restore-notes.md
  git-publication-notes.md
  screenshots/
```

Do not commit secrets, raw workspace keys, passwords, private repository credentials, or DPAPI-unprotected material.

## Release gate

SEC-06 is PASS only when all SEC06-01..17 are PASS with evidence. A GitHub Actions green result alone is insufficient because DPAPI, packaged SQLCipher, Windows profile isolation, and the real UI/deployment lifecycle require Windows UAT.
