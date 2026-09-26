# Clean test database

Create a clean copy only:

```powershell
cd CenterManager
python scripts/create_clean_test_database.py
```

Create and activate a clean copy as the canonical runtime database:

```powershell
cd CenterManager
python scripts/activate_clean_database.py --yes
```

## Activation safety contract

Activation is explicit and fail-closed. **Close CenterManager and any SQLite tools before running it.**

The helper performs these steps:

1. Requires the explicit `--yes` flag.
2. Refuses a runtime database that is actively locked.
3. Checkpoints WAL and refuses activation while `center.db-wal` / `center.db-shm` remain active.
4. Builds `center.clean.db` with the existing online-backup sanitizer.
5. Validates the candidate:
   - `PRAGMA integrity_check == ok`
   - empty `PRAGMA foreign_key_check`
   - exactly one non-empty `alembic_version`
   - zero rows in every application table
6. Rechecks runtime ownership/WAL immediately before replacement.
7. Creates a timestamped safety backup such as:

   ```text
   center.original-20260926-220000-123456.db
   ```

   The backup is a complete copy of the original runtime DB and is retained as recovery evidence.
8. Atomically promotes the clean candidate to `center.db` when the files are on the same filesystem.
9. Re-validates the promoted runtime database.
10. If promotion or post-activation validation fails, automatically restores the original database from the safety backup while keeping the backup file.

The helper never intentionally mutates or deletes the original data before a valid safety backup exists.

## Custom paths

```powershell
python scripts/activate_clean_database.py `
  --source "D:\path\center.db" `
  --clean-copy "D:\path\center.clean.db" `
  --backup "D:\path\center.original.db" `
  --yes
```

The backup path must differ from both the runtime DB and clean candidate and must not already exist.

## Exit codes

- `0`: activation succeeded.
- `1`: activation or validation failed; the original DB remains/restores safely whenever automatic rollback is possible.
- `2`: explicit `--yes` confirmation was not provided.
