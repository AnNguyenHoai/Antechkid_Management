# EP-PROD-06 — Backup/Restore Disaster Recovery UAT

## Purpose

Validate that the production candidate can create a recoverable backup, reject unsafe/corrupt backup material, restore a known-good backup after destructive runtime damage, and restart with the recovered state intact.

This is a physical UAT gate. CI validates the contract/tooling; it does not replace the destructive recovery exercise on an isolated Windows UAT environment.

Base implementation: `main_repos@66f4171d266257deed630f14a2bb3f0ecb96db20`.

## Existing recovery contract under test

`BackupService` owns backups under `runtime/Backup/publish`, stores `center.db`, `metadata`, and `manifest.json`, validates SQLite with `PRAGMA integrity_check`, verifies the database checksum, rejects paths outside the managed backup directory, restores through temporary paths plus `os.replace`, and calls `refresh_runtime_db()` after database replacement.

The Git repository remains the collaboration source of truth. EP-PROD-06 validates local disaster recovery only; it must not silently rewrite the collaboration remote or claim that a local backup supersedes newer authoritative repository data.

## Safety rules

- Run only on an isolated UAT release/runtime copy. Never perform destructive steps against live production data.
- Use synthetic markers only. Do not capture names, phone numbers, payment details, credentials, raw Git remotes, or database content in evidence.
- Keep evidence outside the source repository.
- Record hashes and observations, not database payloads.
- A failed integrity/checksum/path-boundary/restore/restart observation is a failed production gate. Do not manually edit evidence to PASS.
- Before the exercise, retain an independent copy of the whole UAT runtime directory so the UAT environment itself can be recovered.

## Prerequisites

1. EP-PROD-04 database-upgrade gate passed.
2. EP-PROD-05 two-machine collaboration UAT passed.
3. Approved release ZIP/checksum and release manifest are available.
4. One isolated Windows UAT environment is available with a disposable copy of the collaboration repository.
5. Application starts normally before the exercise.
6. Evidence directory exists outside the release tree.

## Required scenarios

The scenario report must contain these IDs exactly once:

- `baseline_backup_create`
- `backup_integrity`
- `restore_after_runtime_damage`
- `metadata_restore`
- `restart_after_restore`
- `corrupt_database_rejected`
- `checksum_mismatch_rejected`
- `outside_path_rejected`
- `newer_format_rejected`
- `collaboration_source_of_truth_preserved`

### 0. Baseline

Start the approved release and create a unique synthetic marker such as `EP-PROD-06-BASELINE-<timestamp>`. Confirm normal read/write behavior before backup.

### 1. Baseline backup create

Create a backup through the application path that invokes `BackupService.create_backup()`.

PASS observations:

- a new directory appears under `runtime/Backup/publish`;
- `manifest.json`, `center.db`, and `metadata/` exist;
- manifest `format_version` is supported;
- backup DB hash equals the manifest checksum;
- SQLite `PRAGMA integrity_check` returns `ok`.

### 2. Backup integrity

Capture evidence for the backup without opening it read/write. The collector must report the backup manifest hash, database hash, manifest checksum match, SQLite integrity result, metadata presence, and managed-path status.

### 3. Restore after runtime damage

After the backup is confirmed good, create a second synthetic marker `EP-PROD-06-AFTER-BACKUP-<timestamp>`. Close the application cleanly, then damage only the isolated UAT runtime DB (for example replace `runtime/Database/center.db` with a known invalid disposable file).

Restore the selected backup through `BackupService.restore_backup()`.

PASS observations:

- restore reports success;
- runtime DB becomes a valid SQLite database;
- restored runtime DB SHA-256 equals the selected backup DB SHA-256;
- baseline marker is present again;
- post-backup marker is absent, proving point-in-time rollback rather than accidental retention of the damaged/newer runtime state.

### 4. Metadata restore

Before backup, place a synthetic harmless marker in runtime metadata. After backup, alter that marker. After restore, confirm the metadata tree reflects the backup version.

### 5. Restart after restore

Fully exit and restart the application after restore.

PASS observations:

- startup completes successfully;
- restored data remains readable;
- no stale SQLAlchemy/session handle keeps the damaged DB alive;
- backup/restore does not leave `.center.db.restore-*`, `.metadata.restore-*`, or `.metadata.previous-*` artifacts after a successful restore.

### 6. Corrupt database rejected

Make a copy of a valid managed backup directory, corrupt its `center.db`, and attempt restore.

PASS: restore is rejected before replacing the active runtime DB. The pre-attempt runtime DB hash remains unchanged.

### 7. Checksum mismatch rejected

Make another managed backup copy, preserve a valid SQLite DB but change it so the manifest checksum no longer matches.

PASS: restore is rejected with checksum validation and active runtime DB remains unchanged.

### 8. Outside path rejected

Copy an otherwise valid backup outside `runtime/Backup/publish` and attempt restore.

PASS: restore is rejected by managed-path boundary validation and active runtime DB remains unchanged.

### 9. Newer format rejected

Copy a valid managed backup and set its manifest `format_version` above `BackupService.FORMAT_VERSION`.

PASS: restore is rejected and active runtime DB remains unchanged.

### 10. Collaboration source of truth preserved

After local restore, reconnect/start normally against the disposable shared collaboration repository.

PASS observations:

- the local backup restore does not push or rewrite the remote by itself;
- normal startup synchronization still treats repository state as authoritative;
- if the remote is newer than the restored local state, startup synchronization rematerializes the newer authoritative repository DB into runtime according to the existing contract.

## Evidence capture

Example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\capture_backup_restore_dr_evidence.ps1 `
  -ReleaseRoot C:\UAT\CenterManager `
  -BackupPath C:\UAT\CenterManager\runtime\Backup\publish\pre_publish_... `
  -Stage final `
  -OutputPath C:\UAT-Evidence\ep-prod-06-final.json
```

The evidence collector is read-only. It must not run restore or modify the backup/runtime database.

## Scenario report

Create `ep-prod-06-scenarios.json`:

```json
{
  "schema_version": 1,
  "task": "EP-PROD-06",
  "scenarios": [
    {"scenario": "baseline_backup_create", "status": "PASS"},
    {"scenario": "backup_integrity", "status": "PASS"},
    {"scenario": "restore_after_runtime_damage", "status": "PASS"},
    {"scenario": "metadata_restore", "status": "PASS"},
    {"scenario": "restart_after_restore", "status": "PASS"},
    {"scenario": "corrupt_database_rejected", "status": "PASS"},
    {"scenario": "checksum_mismatch_rejected", "status": "PASS"},
    {"scenario": "outside_path_rejected", "status": "PASS"},
    {"scenario": "newer_format_rejected", "status": "PASS"},
    {"scenario": "collaboration_source_of_truth_preserved", "status": "PASS"}
  ]
}
```

## Automated verification

```powershell
python scripts\verify_backup_restore_dr_uat.py `
  --evidence C:\UAT-Evidence\ep-prod-06-final.json `
  --scenario-report C:\UAT-Evidence\ep-prod-06-scenarios.json
```

The verifier fails closed unless:

- evidence schema/task are correct;
- release version and source commit are present;
- backup path is reported as managed;
- manifest, backup DB, and runtime DB hashes are present;
- SQLite integrity is `ok`;
- manifest checksum equals the backup DB hash;
- metadata is present;
- final runtime DB hash equals the selected backup DB hash;
- no temporary restore artifacts remain;
- all ten required physical scenarios exist exactly once and are `PASS`.

## Completion gate

EP-PROD-06 is complete only when the physical UAT observations and the automated evidence verifier both PASS. Hash equality proves file-level recovery; the operator must still verify the synthetic business markers, restart behavior, rejection messages, and collaboration source-of-truth behavior described above.
