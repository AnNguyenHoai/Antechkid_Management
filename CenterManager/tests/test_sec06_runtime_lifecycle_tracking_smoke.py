from pathlib import Path

from centermanager.database import engine as database_engine


def test_tracked_runtime_lifecycle_wrapper_unregisters_raw_handle(monkeypatch):
    events = []

    class _Raw:
        def execute(self, statement):
            return None

        def close(self):
            events.append("closed")

    raw = _Raw()

    def fake_connect(path, key, *, allow_create, readonly=False, runtime_guarded=False):
        assert runtime_guarded is True
        database_engine._register_runtime_dbapi_connection(raw)
        return raw

    monkeypatch.setattr(database_engine, "_connect_encrypted", fake_connect)
    lifecycle = database_engine._runtime_lifecycle(
        Path("center.db"), b"x" * 32, runtime_guarded=True
    )
    connection = lifecycle._connect_readonly()
    assert database_engine.runtime_dbapi_connection_count() >= 1
    connection.close()
    assert events == ["closed"]
    assert id(raw) not in database_engine._runtime_dbapi_connections
