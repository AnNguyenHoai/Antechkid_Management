from pathlib import Path

from centermanager.database import engine as database_engine


def test_runtime_lifecycle_routes_readonly_sqlcipher_open_through_runtime_guard(monkeypatch):
    captured = {}

    class _Connection:
        def execute(self, statement):
            captured["statement"] = statement
            return self

        def fetchone(self):
            return ("ok",)

        def close(self):
            captured["closed"] = True

    def fake_connect(path, key, *, allow_create, readonly=False, runtime_guarded=False):
        captured.update(
            path=Path(path),
            allow_create=allow_create,
            readonly=readonly,
            runtime_guarded=runtime_guarded,
        )
        return _Connection()

    monkeypatch.setattr(database_engine, "_connect_encrypted", fake_connect)
    lifecycle = database_engine._runtime_lifecycle(
        Path("center.db"),
        b"x" * 32,
        runtime_guarded=True,
    )

    connection = lifecycle._connect_readonly()
    connection.close()

    assert captured["allow_create"] is False
    assert captured["readonly"] is True
    assert captured["runtime_guarded"] is True
    assert captured["closed"] is True
