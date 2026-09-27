# -*- coding: utf-8 -*-
from pathlib import Path

import centermanager.database.migration as migration


class _FakeEngine:
    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True


def test_runtime_upgrade_uses_production_engine(monkeypatch, tmp_path):
    db = tmp_path / "center.db"
    db.write_bytes(b"ciphertext")
    engine = _FakeEngine()
    called = {}

    monkeypatch.setattr(migration, "get_database_path", lambda: db)
    monkeypatch.setattr(migration, "create_production_engine", lambda echo=False: engine)

    def fake_upgrade(path: Path, supplied_engine):
        called["path"] = path
        called["engine"] = supplied_engine

    monkeypatch.setattr(migration, "_upgrade_database_with_engine", fake_upgrade)

    migration.upgrade_database_to_head()

    assert called["path"] == db
    assert called["engine"] is engine
    assert engine.disposed is True


def test_explicit_path_upgrade_remains_plain_disposable_boundary(monkeypatch, tmp_path):
    db = tmp_path / "dev.db"
    db.write_bytes(b"sqlite")
    engine = _FakeEngine()
    called = {}

    monkeypatch.setattr(
        migration,
        "create_engine_for_path",
        lambda path, allow_create=False: engine,
    )

    def fake_upgrade(path: Path, supplied_engine):
        called["path"] = path
        called["engine"] = supplied_engine

    monkeypatch.setattr(migration, "_upgrade_database_with_engine", fake_upgrade)

    migration.upgrade_database_path_to_head(db)

    assert called["path"] == db.resolve()
    assert called["engine"] is engine
    assert engine.disposed is True
