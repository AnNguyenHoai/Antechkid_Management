import sqlite3
from pathlib import Path

import pytest

from centermanager.database import artifact_security
from centermanager.database import engine as database_engine
from centermanager.platform.backup import backup_service


class _Row:
    def __init__(self, value="ok"):
        self._value = value

    def fetchone(self):
        return (self._value,)


class _FakeConnection:
    def __init__(self):
        self.closed = False
        self.backup_target = None

    def execute(self, statement):
        return _Row("ok")

    def backup(self, destination):
        assert id(self) in database_engine._runtime_dbapi_connections
        self.backup_target = destination

    def close(self):
        assert id(self) in database_engine._runtime_dbapi_connections or self.closed
        self.closed = True


def test_runtime_db_boundary_tracks_owner_and_unregisters_after_native_close():
    baseline = database_engine.runtime_dbapi_connection_count()
    raw = _FakeConnection()

    with database_engine.runtime_dbapi_connection(
        lambda: raw,
        owner="unit-test-owner",
    ) as connection:
        assert connection is raw
        assert database_engine.runtime_dbapi_connection_count() == baseline + 1
        details = dict(database_engine.runtime_dbapi_connection_details())
        assert details[id(raw)].owner == "unit-test-owner"
        assert details[id(raw)].thread_id
        assert details[id(raw)].stack

    assert raw.closed is True
    assert database_engine.runtime_dbapi_connection_count() == baseline
    assert id(raw) not in database_engine._runtime_dbapi_connections


def test_runtime_db_boundary_rejects_new_open_while_maintenance_is_active():
    opened = []
    database_engine.begin_runtime_db_maintenance()
    try:
        with pytest.raises(database_engine.RuntimeDatabaseMaintenanceError):
            database_engine.acquire_runtime_dbapi_connection(
                lambda: opened.append(True),
                owner="must-not-open",
            )
    finally:
        database_engine.end_runtime_db_maintenance()

    assert opened == []


def test_maintenance_owned_handle_requires_active_fence():
    raw = _FakeConnection()

    with pytest.raises(database_engine.RuntimeDatabaseMaintenanceError):
        database_engine.acquire_runtime_dbapi_connection(
            lambda: raw,
            owner="recovery-only",
            maintenance_owned=True,
        )

    assert raw.closed is False
    assert id(raw) not in database_engine._runtime_dbapi_connections


def test_backup_post_swap_validation_is_tracked_during_maintenance(tmp_path, monkeypatch):
    db_path = tmp_path / "center.db"
    db_path.write_bytes(b"not-empty")
    raw = _FakeConnection()
    observations = []

    def fake_connect(*args, **kwargs):
        observations.append(database_engine.runtime_db_maintenance_active())
        return raw

    monkeypatch.setattr(backup_service.sqlite3, "connect", fake_connect)

    database_engine.begin_runtime_db_maintenance()
    try:
        error = backup_service.BackupService._validate_plain_sqlite(
            db_path,
            runtime_guarded=True,
            maintenance_owned=True,
        )
    finally:
        database_engine.end_runtime_db_maintenance()

    assert error is None
    assert observations == [True]
    assert raw.closed is True
    assert id(raw) not in database_engine._runtime_dbapi_connections


def test_lifecycle_wrapper_adopts_untracked_handle_without_double_close_on_unwind():
    class _CountingConnection:
        def __init__(self):
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    raw = _CountingConnection()
    wrapper = database_engine._TrackedLifecycleConnection(
        raw,
        owner="unit-test-lifecycle",
    )

    assert id(raw) in database_engine._runtime_dbapi_connections
    details = dict(database_engine.runtime_dbapi_connection_details())
    assert details[id(raw)].owner == "unit-test-lifecycle"

    # Simulate recovery force-close: native handle closes and leaves the active
    # registry before the original lifecycle owner unwinds its context.
    raw.close()
    database_engine._unregister_runtime_dbapi_connection(raw)
    wrapper.close()

    assert raw.close_calls == 1
    assert id(raw) not in database_engine._runtime_dbapi_connections


def test_sqlalchemy_registry_remains_visible_until_native_driver_close(tmp_path, monkeypatch):
    events = []
    real_connect = sqlite3.connect

    class _TrackingConnection(sqlite3.Connection):
        def close(self):
            assert id(self) in database_engine._runtime_dbapi_connections
            events.append("native-close")
            return super().close()

    def fake_connect_plain(path, *, allow_create, readonly=False):
        return real_connect(
            path,
            factory=_TrackingConnection,
            check_same_thread=False,
        )

    monkeypatch.setattr(database_engine, "_connect_plain", fake_connect_plain)
    engine = database_engine.create_engine_for_path(
        tmp_path / "center.db",
        allow_create=True,
        runtime_guarded=True,
    )

    connection = engine.connect()
    raw = connection.connection.driver_connection
    assert id(raw) in database_engine._runtime_dbapi_connections

    connection.close()

    assert events == ["native-close"]
    assert id(raw) not in database_engine._runtime_dbapi_connections
    engine.dispose()


def test_artifact_runtime_validation_is_visible_to_process_registry(tmp_path, monkeypatch):
    db_path = tmp_path / "center.db"
    db_path.write_bytes(b"not-empty")
    raw = _FakeConnection()

    monkeypatch.setattr(artifact_security.sqlite3, "connect", lambda *args, **kwargs: raw)

    artifact_security._validate_plain_database(db_path, runtime_guarded=True)

    assert raw.closed is True
    assert id(raw) not in database_engine._runtime_dbapi_connections


def test_backup_runtime_snapshot_source_is_tracked_until_native_close(tmp_path, monkeypatch):
    source_path = tmp_path / "center.db"
    source_path.write_bytes(b"source")
    destination_path = tmp_path / "backup.db"
    source = _FakeConnection()

    class _Destination:
        def close(self):
            pass

    destination = _Destination()

    def fake_connect(target, *args, **kwargs):
        if str(target).startswith("file:"):
            return source
        return destination

    monkeypatch.setattr(backup_service.sqlite3, "connect", fake_connect)

    backup_service.BackupService._copy_plain_sqlite_snapshot(
        source_path,
        destination_path,
        runtime_guarded=True,
    )

    assert source.backup_target is destination
    assert source.closed is True
    assert id(source) not in database_engine._runtime_dbapi_connections
