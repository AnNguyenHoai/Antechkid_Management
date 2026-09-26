from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "create_clean_test_database.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("create_clean_test_database", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL
            );
            CREATE TRIGGER trg_parent_delete
            AFTER DELETE ON parents
            BEGIN
                INSERT INTO audit_log(message) VALUES ('parent deleted');
            END;

            INSERT INTO parents(name) VALUES ('real-data');
            INSERT INTO children(parent_id, name) VALUES (1, 'child-data');
            INSERT INTO audit_log(message) VALUES ('existing-audit');
            """
        )


def test_clean_copy_keeps_schema_and_revision_but_removes_all_application_rows(tmp_path):
    module = _load_script_module()
    source = tmp_path / "source.db"
    output = tmp_path / "clean.db"
    _seed_source(source)

    module.create_clean_database(source, output)

    # The source is a read-only input to the script and must remain untouched.
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1

    with sqlite3.connect(output) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "1e10a038"

        for table in ("parents", "children", "audit_log"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

        trigger = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type='trigger' AND name='trg_parent_delete'"
        ).fetchone()
        assert trigger is not None

        # sqlite_sequence is reset, so a fresh test starts from the initial IDs.
        assert connection.execute("SELECT COUNT(*) FROM sqlite_sequence").fetchone()[0] == 0
        connection.execute("INSERT INTO parents(name) VALUES ('fresh-test-data')")
        assert connection.execute("SELECT id FROM parents").fetchone()[0] == 1


def test_existing_output_requires_explicit_force(tmp_path):
    module = _load_script_module()
    source = tmp_path / "source.db"
    output = tmp_path / "clean.db"
    _seed_source(source)
    output.write_bytes(b"do-not-overwrite")

    with pytest.raises(module.CleanDatabaseError, match="--force"):
        module.create_clean_database(source, output)

    assert output.read_bytes() == b"do-not-overwrite"


def test_force_replaces_only_output_never_source(tmp_path):
    module = _load_script_module()
    source = tmp_path / "source.db"
    output = tmp_path / "clean.db"
    _seed_source(source)
    before = source.read_bytes()
    output.write_bytes(b"replace-me")

    module.create_clean_database(source, output, force=True)

    assert source.read_bytes() == before
    with sqlite3.connect(output) as connection:
        assert connection.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 0


def test_refuses_to_overwrite_source_even_with_force(tmp_path):
    module = _load_script_module()
    source = tmp_path / "source.db"
    _seed_source(source)

    with pytest.raises(module.CleanDatabaseError, match="different from the source"):
        module.create_clean_database(source, source, force=True)
