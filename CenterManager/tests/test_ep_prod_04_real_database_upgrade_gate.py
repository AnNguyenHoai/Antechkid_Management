# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from centermanager.database import upgrade_gate
from centermanager.database.upgrade_gate import (
    DatabaseUpgradeGateError,
    assert_preserved_rows,
    create_consistent_snapshot,
    inspect_database_health,
    run_database_upgrade_gate,
)


def _create_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE attendance ("
            "id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, "
            "FOREIGN KEY(student_id) REFERENCES students(id))"
        )
        connection.execute("INSERT INTO students(id, name) VALUES (1, 'An')")
        connection.execute("INSERT INTO attendance(id, student_id) VALUES (10, 1)")
        connection.commit()
    finally:
        connection.close()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_prod_04_snapshot_is_separate_and_source_remains_unchanged(tmp_path):
    source = tmp_path / "center.db"
    snapshot = tmp_path / "evidence" / "snapshot.db"
    _create_database(source)
    source_hash = _sha(source)

    create_consistent_snapshot(source, snapshot)

    assert snapshot.exists()
    assert snapshot.resolve() != source.resolve()
    assert _sha(source) == source_hash
    health = inspect_database_health(snapshot)
    assert health.integrity_check == "ok"
    assert health.foreign_key_violations == 0
    assert health.table_counts == {"attendance": 1, "students": 1}


def test_prod_04_refuses_to_use_source_as_snapshot(tmp_path):
    source = tmp_path / "center.db"
    _create_database(source)

    with pytest.raises(DatabaseUpgradeGateError, match="must differ"):
        create_consistent_snapshot(source, source)


def test_prod_04_row_preservation_is_fail_closed():
    assert_preserved_rows({"students": 10, "attendance": 8}, {"students": 10, "attendance": 8})

    with pytest.raises(DatabaseUpgradeGateError, match="row-count changes"):
        assert_preserved_rows(
            {"students": 10, "attendance": 8},
            {"students": 9, "attendance": 8},
        )

    with pytest.raises(DatabaseUpgradeGateError, match="missing tables"):
        assert_preserved_rows({"students": 10}, {})


def test_prod_04_gate_upgrades_only_snapshot_and_emits_evidence(tmp_path, monkeypatch):
    source = tmp_path / "center.db"
    evidence = tmp_path / "evidence"
    _create_database(source)
    source_hash = _sha(source)
    revisions = iter(["old-revision", "head-revision", "head-revision"])
    migrated_paths = []

    monkeypatch.setattr(
        upgrade_gate,
        "get_current_revision",
        lambda _path: next(revisions),
    )
    monkeypatch.setattr(
        upgrade_gate,
        "get_head_revision",
        lambda _path: "head-revision",
    )

    def fake_upgrade(database_path: Path) -> None:
        migrated_paths.append(Path(database_path).resolve())
        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                "CREATE TABLE migration_marker (id INTEGER PRIMARY KEY, note TEXT)"
            )
            connection.commit()
        finally:
            connection.close()

    monkeypatch.setattr(upgrade_gate, "upgrade_database_path_to_head", fake_upgrade)

    report = run_database_upgrade_gate(source, evidence)

    assert report.status == "passed"
    assert report.source_revision == "old-revision"
    assert report.target_revision == "head-revision"
    assert report.upgraded_revision == "head-revision"
    assert report.reopened_revision == "head-revision"
    assert report.source_preserved is True
    assert report.source_sha256_before_snapshot == source_hash
    assert report.source_sha256_after_snapshot == source_hash
    assert report.integrity_after_reopen == "ok"
    assert report.foreign_key_violations_after_reopen == 0
    assert report.table_counts_before == {"attendance": 1, "students": 1}
    assert report.table_counts_after["attendance"] == 1
    assert report.table_counts_after["students"] == 1
    assert report.snapshot_sha256_before_upgrade != report.snapshot_sha256_after_upgrade
    assert migrated_paths == [(evidence / "center.upgrade-rehearsal.db").resolve()]
    assert migrated_paths[0] != source.resolve()
    assert _sha(source) == source_hash
    assert (evidence / "database-upgrade-report.json").exists()


def test_prod_04_gate_rejects_foreign_key_corruption(tmp_path):
    database = tmp_path / "broken.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER, "
            "FOREIGN KEY(parent_id) REFERENCES parent(id))"
        )
        connection.execute("INSERT INTO child(id, parent_id) VALUES (1, 999)")
        connection.commit()
    finally:
        connection.close()

    health = inspect_database_health(database)
    assert health.integrity_check == "ok"
    assert health.foreign_key_violations == 1

    with pytest.raises(DatabaseUpgradeGateError, match="foreign-key"):
        upgrade_gate.assert_healthy(health, phase="pre-upgrade")


def test_prod_04_migration_api_is_path_aware_source_contract():
    import inspect
    from centermanager.database import migration

    source = inspect.getsource(migration)
    assert "def upgrade_database_path_to_head(database_path: Path)" in source
    assert "allow_create=False" in source
    assert "def upgrade_database_to_head()" in source
    assert "upgrade_database_path_to_head(get_database_path())" in source
