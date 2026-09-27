# -*- coding: utf-8 -*-
from pathlib import Path

import centermanager.database.startup_security as startup_security
from centermanager.database.startup_security import (
    StartupDatabaseReadiness,
    inspect_authoritative_database_for_startup,
)


def test_windows_production_plaintext_authoritative_db_requires_controlled_migration(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ANTECHKIDS_FORCE_DATABASE_ENCRYPTION", "1")
    db = tmp_path / "center.db"
    db.write_bytes(b"SQLite format 3\x00" + b"x" * 64)

    result = inspect_authoritative_database_for_startup(db)

    assert result.state is StartupDatabaseReadiness.PLAINTEXT_MIGRATION_REQUIRED
    assert "controlled SEC-01" in result.message


def test_encrypted_authoritative_db_without_local_workspace_key_requires_provisioning(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ANTECHKIDS_FORCE_DATABASE_ENCRYPTION", "1")
    db = tmp_path / "center.db"
    db.write_bytes(b"SQLCIPHER-CIPHERTEXT" + b"x" * 64)
    missing_bundle = tmp_path / "missing-database-key.dpapi"

    class _MissingKeyStore:
        @property
        def bundle_path(self) -> Path:
            return missing_bundle

    monkeypatch.setattr(startup_security, "DatabaseKeyStore", _MissingKeyStore)

    result = inspect_authoritative_database_for_startup(db)

    assert result.state is StartupDatabaseReadiness.KEY_PROVISIONING_REQUIRED
    assert "do not generate a new key" in result.message


def test_missing_authoritative_db_is_reported_before_runtime_materialization(tmp_path):
    result = inspect_authoritative_database_for_startup(tmp_path / "center.db")
    assert result.state is StartupDatabaseReadiness.MISSING
