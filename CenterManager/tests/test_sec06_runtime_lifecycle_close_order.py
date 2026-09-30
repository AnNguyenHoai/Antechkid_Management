from pathlib import Path

from centermanager.database import engine as database_engine


def test_runtime_lifecycle_native_close_happens_before_registry_removal(monkeypatch):
    events = []

    class _Raw:
        def execute(self, statement):
            return None

        def close(self):
            assert id(self) in database_engine._runtime_dbapi_connections
            events.append("native-close")

    raw = _Raw()

    def fake_connect(path, key, *, allow_create, readonly=False, runtime_guarded=False):
        database_engine._register_runtime_dbapi_connection(raw)
        return raw

    monkeypatch.setattr(database_engine, "_connect_encrypted", fake_connect)
    lifecycle = database_engine._runtime_lifecycle(
        Path("center.db"), b"x" * 32, runtime_guarded=True
    )
    connection = lifecycle._connect_readonly()
    connection.close()

    assert events == ["native-close"]
    assert id(raw) not in database_engine._runtime_dbapi_connections
