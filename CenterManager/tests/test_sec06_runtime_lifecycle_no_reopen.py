from pathlib import Path

import pytest

from centermanager.database import engine as database_engine


def test_runtime_lifecycle_connector_cannot_reopen_db_during_maintenance(monkeypatch):
    opened = []

    def fake_open(path, key, *, allow_create, readonly=False, runtime_guarded=False):
        if runtime_guarded and database_engine.runtime_db_maintenance_active():
            raise database_engine.RuntimeDatabaseMaintenanceError("maintenance")
        opened.append(Path(path))
        raise AssertionError("unexpected open")

    monkeypatch.setattr(database_engine, "_connect_encrypted", fake_open)
    lifecycle = database_engine._runtime_lifecycle(
        Path("center.db"), b"x" * 32, runtime_guarded=True
    )

    database_engine.begin_runtime_db_maintenance()
    try:
        with pytest.raises(database_engine.RuntimeDatabaseMaintenanceError):
            lifecycle._connect_readonly()
    finally:
        database_engine.end_runtime_db_maintenance()

    assert opened == []
