from pathlib import Path

from centermanager.database import engine as database_engine


class _RawConnection:
    def __init__(self):
        self.closed = False

    def cursor(self):
        return _Cursor()

    def execute(self, statement):
        return _Result((1,))

    def close(self):
        self.closed = True


class _Cursor:
    def execute(self, statement):
        if statement == "PRAGMA cipher_version;":
            return _Result(("4.0",))
        return self

    def close(self):
        pass


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


def test_guarded_encrypted_connection_is_registered_until_native_close(monkeypatch, tmp_path):
    raw = _RawConnection()

    class _Driver:
        @staticmethod
        def connect(*args, **kwargs):
            return raw

    monkeypatch.setattr(database_engine, "load_sqlcipher_driver", lambda: _Driver)
    monkeypatch.setattr(database_engine, "apply_sqlcipher_key", lambda connection, key: None)

    connection = database_engine._connect_encrypted(
        Path(tmp_path) / "center.db",
        b"x" * 32,
        allow_create=False,
        readonly=True,
        runtime_guarded=True,
    )
    try:
        assert connection is raw
        assert database_engine.runtime_dbapi_connection_count() >= 1
    finally:
        raw.close()
        database_engine._unregister_runtime_dbapi_connection(raw)

    assert raw.closed is True
