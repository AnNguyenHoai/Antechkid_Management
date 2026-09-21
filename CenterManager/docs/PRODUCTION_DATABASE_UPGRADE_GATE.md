# EP-PROD-04 — Real Database Upgrade Gate

This gate must be executed against a recent production-like `center.db` before approving a production release candidate.

## Safety contract

- Never run Alembic directly on the source database during rehearsal.
- The source database is opened read-only.
- SQLite Backup API creates a transactionally consistent snapshot, including committed WAL state.
- Alembic upgrades only the snapshot copy.
- `release-evidence/` is ignored by Git because it can contain a full copy of production data.
- Store approved evidence only in the designated restricted release-evidence location outside the repository.

## Run

From `CenterManager/`:

```bash
python scripts/verify_production_database_upgrade.py --database "D:\path\to\center.db"
```

Optional evidence root:

```bash
python scripts/verify_production_database_upgrade.py \
  --database "D:\path\to\center.db" \
  --evidence-root "D:\CenterManagerReleaseEvidence"
```

Each run creates a timestamped directory containing:

- `center.upgrade-rehearsal.db` — upgraded snapshot copy.
- `database-upgrade-report.json` — machine-readable evidence.

## PASS contract

The gate passes only when all of the following are true:

1. Source database exists and can be snapshotted without write access.
2. Pre-upgrade `PRAGMA integrity_check` returns `ok`.
3. Pre-upgrade `PRAGMA foreign_key_check` returns no violations.
4. The same production Alembic migration implementation upgrades the snapshot to the current migration head.
5. Post-upgrade `PRAGMA integrity_check` returns `ok`.
6. Post-upgrade `PRAGMA foreign_key_check` returns no violations.
7. The upgraded revision exactly equals the current Alembic head.
8. Every business table that existed before migration still exists.
9. Every pre-existing business table preserves its row count.

The row-count rule is intentionally fail-closed. If a future migration intentionally transforms or deletes business rows, that migration requires an explicit reviewed exception to the gate rather than silently weakening the default invariant.

## Release evidence review

Before Go-Live, record at minimum:

- release version and source commit;
- source DB backup/snapshot date;
- gate timestamp;
- source revision;
- target revision;
- upgraded revision;
- snapshot SHA-256 before migration;
- integrity/FK results;
- pre/post table row counts;
- reviewer approval.

Do not commit the database snapshot or production-derived report to GitHub if paths/counts are considered operationally sensitive.
