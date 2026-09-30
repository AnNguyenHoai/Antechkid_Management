from centermanager.database import engine as database_engine


class _RawConnection:
    def __init__(self):
        self.closed = False

    def execute(self, statement):
        if statement == "PRAGMA integrity_check":
            return _Result(("ok",))
        return _Result(("table",))

    def close(self):
        self.closed = True


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


def test_runtime_lifecycle_readonly_handle_is_unregistered_only_after_close(monkeypatch, tmp_path):
    db_path = tmp_path / "center.db"
    db_path.write_bytes(b"database")
    raw = _RawConnection()

    monkeypatch.setattr(database_engine, "load_sqlcipher_driver", lambda: None)
    monkeypatch.setattr(
        database_engine,
        "_connect_encrypted",
        lambda path, key, *, allow_create, readonly=False, runtime_guarded=False: (
            database_engine._register_runtime_dbapi_connection(raw) or raw
        ),
    )

    lifecycle = database_engine._runtime_lifecycle(
        db_path,
        b"x" * 32,
        runtime_guarded=True,
    )
    assert lifecycle.inspect().value == "available"
    assert raw.closed is True
    assert database_engine.runtime_dbapi_connection_count() == 0


def test_runtime_inspection_is_blocked_by_maintenance_fence(monkeypatch, tmp_path):
    db_path = tmp_path / "center.db"
    db_path.write_bytes(b"database")
    monkeypatch.setattr(database_engine, "get_database_path", lambda: db_path)
    monkeypatch.setattr(database_engine, "database_encryption_required", lambda: True)
    monkeypatch.setattr(database_engine.DatabaseKeyStore, "load", lambda self: b"x" * 32)

    database_engine.begin_runtime_db_maintenance()
    try:
        state = database_engine.inspect_runtime_database()
        # DatabaseLifecycle deliberately converts connector failures to a recovery
        # state; the important contract is that maintenance cannot open a handle.
        assert state.value == "corrupted"
        assert database_engine.runtime_dbapi_connection_count() == 0
    finally:
        database_engine.end_runtime_db_maintenance()
