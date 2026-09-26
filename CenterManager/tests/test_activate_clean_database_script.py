from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "activate_clean_database.py"


def _load_script_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("activate_clean_database", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _seed_source(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            );
            INSERT INTO alembic_version(version_num) VALUES ('1e10a038');

            CREATE TABLE parents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                FOREIGN KEY(parent_id) REFERENCES parents(id)
            );
            INSERT INTO parents(name) VALUES ('real-data');
            INSERT INTO children(parent_id, name) VALUES (1, 'child-data');
            """
        )


def test_activation_requires_explicit_yes(tmp_path, capsys):
    module = _load_script_module()
    source = tmp_path / "center.db"
    clean = tmp_path / "center.clean.db"
    _seed_source(source)

    rc = module.main(["--source", str(source), "--clean-copy", str(clean)])

    assert rc == 2
    assert "without --yes" in capsys.readouterr().err
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 1


def test_activation_creates_clean_runtime_and_preserves_original_backup(tmp_path):
    module = _load_script_module()
    source = tmp_path / "center.db"
    clean = tmp_path / "center.clean.db"
    backup = tmp_path / "center.original.db"
    _seed_source(source)

    active, created_backup = module.activate(source, clean, backup)

    assert active == source.resolve()
    assert created_backup == backup.resolve()
    assert backup.exists()
    assert not clean.exists()

    with sqlite3.connect(source) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "1e10a038"
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 0

    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "1e10a038"
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 1


def test_activation_refuses_locked_runtime_database(tmp_path):
    module = _load_script_module()
    source = tmp_path / "center.db"
    clean = tmp_path / "center.clean.db"
    _seed_source(source)

    blocker = sqlite3.connect(source)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(module.ActivationError, match="busy|Close CenterManager"):
            module.activate(source, clean)
    finally:
        blocker.rollback()
        blocker.close()

    assert not clean.exists()
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 1


def test_post_promotion_validation_failure_restores_original_and_keeps_backup(
    tmp_path, monkeypatch
):
    module = _load_script_module()
    source = tmp_path / "center.db"
    clean = tmp_path / "center.clean.db"
    backup = tmp_path / "center.original.db"
    _seed_source(source)

    real_validate = module._validate_clean_database
    source_path = source.resolve()
    validation_calls = {"source": 0}

    def fail_after_promotion(path):
        resolved = Path(path).resolve()
        if resolved == source_path:
            validation_calls["source"] += 1
            raise module.ActivationError("simulated post-promotion validation failure")
        return real_validate(path)

    monkeypatch.setattr(module, "_validate_clean_database", fail_after_promotion)

    with pytest.raises(module.ActivationError, match="original database restored"):
        module.activate(source, clean, backup)

    assert validation_calls["source"] == 1
    assert backup.exists()
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 1
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 1


def test_clean_validation_rejects_application_rows(tmp_path):
    module = _load_script_module()
    candidate = tmp_path / "not-clean.db"
    _seed_source(candidate)

    with pytest.raises(module.ActivationError, match="application rows"):
        module._validate_clean_database(candidate)


def test_default_backup_names_do_not_collide(tmp_path, monkeypatch):
    module = _load_script_module()
    source = tmp_path / "center.db"
    _seed_source(source)

    class FixedDateTime:
        @classmethod
        def now(cls):
            class Value:
                @staticmethod
                def strftime(_format):
                    return "20260926-220000-000000"

            return Value()

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    first = module._default_backup_path(source)
    first.touch()
    second = module._default_backup_path(source)

    assert first != second
    assert second.name.endswith("-1.db")
