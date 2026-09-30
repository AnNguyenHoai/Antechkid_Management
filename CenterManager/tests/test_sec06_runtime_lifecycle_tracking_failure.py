from pathlib import Path

import pytest

from centermanager.database import engine as database_engine


def test_lifecycle_wrapper_preserves_registry_when_native_close_fails(monkeypatch):
    class _Raw:
        def execute(self, statement):
            return None

        def close(self):
            raise OSError("simulated Windows close failure")

    raw = _Raw()

    def fake_connect(path, key, *, allow_create, readonly=False, runtime_guarded=False):
        database_engine._register_runtime_dbapi_connection(raw)
        return raw

    monkeypatch.setattr(database_engine, "_connect_encrypted", fake_connect)
    lifecycle = database_engine._runtime_lifecycle(
        Path("center.db"), b"x" * 32, runtime_guarded=True
    )
    connection = lifecycle._connect_readonly()

    with pytest.raises(OSError):
        connection.close()

    try:
        assert id(raw) in database_engine._runtime_dbapi_connections
    finally:
        database_engine._unregister_runtime_dbapi_connection(raw)
