from contextlib import contextmanager

import pytest

import centermanager.database.migration as migration


class _FakeEngine:
    def __init__(self):
        self.disposed = False

    @contextmanager
    def connect(self):
        yield object()

    def dispose(self):
        self.disposed = True


def test_fresh_runtime_migration_uses_explicit_encrypted_creation_boundary(tmp_path, monkeypatch):
    database = tmp_path / "center.db"
    database.write_bytes(b"encrypted-container")
    key = b"k" * 32
    engine = _FakeEngine()
    captured = {}

    monkeypatch.setattr(migration, "get_database_path", lambda: database)
    monkeypatch.setattr(migration, "database_encryption_required", lambda: True)
    monkeypatch.setattr(migration.DatabaseKeyStore, "load", lambda self: key)

    def fake_create_engine(path, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return engine

    monkeypatch.setattr(migration, "create_engine_for_path", fake_create_engine)
    monkeypatch.setattr(
        migration,
        "_upgrade_database_with_engine",
        lambda path, supplied_engine: captured.update(
            upgraded_path=path, supplied_engine=supplied_engine
        ),
    )

    migration.upgrade_fresh_runtime_database_to_head()

    assert captured["path"] == database
    assert captured["allow_create"] is True
    assert captured["encrypted"] is True
    assert captured["encryption_key"] == key
    assert captured["upgraded_path"] == database
    assert captured["supplied_engine"] is engine
    assert engine.disposed is True


def test_fresh_runtime_migration_rejects_missing_container(tmp_path, monkeypatch):
    database = tmp_path / "center.db"
    monkeypatch.setattr(migration, "get_database_path", lambda: database)

    with pytest.raises(RuntimeError, match="missing or empty"):
        migration.upgrade_fresh_runtime_database_to_head()


def test_normal_production_upgrade_still_uses_fail_closed_engine(monkeypatch, tmp_path):
    database = tmp_path / "center.db"
    database.write_bytes(b"existing-operational-db")
    engine = _FakeEngine()
    calls = {"production_engine": 0}

    monkeypatch.setattr(migration, "get_database_path", lambda: database)

    def fake_production_engine(echo=False):
        calls["production_engine"] += 1
        return engine

    monkeypatch.setattr(migration, "create_production_engine", fake_production_engine)
    monkeypatch.setattr(migration, "_upgrade_database_with_engine", lambda path, supplied: None)

    migration.upgrade_database_to_head()

    assert calls["production_engine"] == 1
    assert engine.disposed is True
