# Clean test database

Create a clean copy only:

```powershell
python scripts/create_clean_test_database.py
```

Create a clean copy and activate it as the canonical runtime database:

```powershell
python scripts/activate_clean_database.py --yes
```

Activation is explicit and fail-closed. Close CenterManager before running it. The current `center.db` is moved to a timestamped `center.original-YYYYMMDD-HHMMSS.db` backup before the clean copy is atomically promoted to `center.db`. If promotion fails, the original database is restored.

The activation helper validates SQLite integrity and foreign keys before and after activation. It never silently deletes the original runtime database.
