# FINAL HARDENING 4 — Full Regression & Baseline Freeze

## Verification baseline
This task closes the final hardening cycle before Employee Workspace development.

## Changes
- Restored a project-level `alembic.ini` so migration regression tests and Alembic commands resolve the migration environment consistently.
- Added source regression contracts for ADMIN 1.5 Configuration Lifecycle.
- Added source regression contracts for ADMIN 1.6 System Operations.
- Added source regression contracts for ADMIN 1.7 Backup & Recovery.
- Added integration regression coverage for ADMIN 1.8 / final Admin hardening.
- Fixed the missing `Event` import in `HighlightTimelineHandler`, which previously caused test collection to fail.
- Integrated `SettingsPage` with `ConfigurationService`, including validation, dirty-state indication, and restart-required semantics.
- Added `scripts/run_final_hardening_4.py` as the focused release verification runner.
- Removed Python cache and pytest cache artifacts from the baseline package.

## Verified in hardening environment
- `python -m compileall -q src` — PASS
- Focused migration + Admin regression suite — 35 passed

## Release gate
Before declaring a local production baseline, run from the project's own fully provisioned `.venv`:

```powershell
python scripts/run_final_hardening_4.py
pytest -q
```

The first command is the required focused baseline gate. The second is the full-project gate and requires all desktop/runtime dependencies such as PySide6 to be installed in the local environment.
