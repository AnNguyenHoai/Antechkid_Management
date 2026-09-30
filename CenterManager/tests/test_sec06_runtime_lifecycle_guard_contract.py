from pathlib import Path

import pytest

from centermanager.database import engine as database_engine


def test_maintenance_fence_blocks_guarded_sqlcipher_before_driver_open(monkeypatch, tmp_path):
    opened = []

    class _Driver:
        @staticmethod
        def connect(*args, **kwargs):
            opened.append(True)
            raise AssertionError("driver must not be opened while maintenance is active")

    monkeypatch.setattr(database_engine, "load_sqlcipher_driver", lambda: _Driver)
    database_engine.begin_runtime_db_maintenance()
    try:
        with pytest.raises(database_engine.RuntimeDatabaseMaintenanceError):
            database_engine._connect_encrypted(
                Path(tmp_path) / "center.db",
                b"x" * 32,
                allow_create=False,
                readonly=True,
                runtime_guarded=True,
            )
    finally:
        database_engine.end_runtime_db_maintenance()

    assert opened == []
