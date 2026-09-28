import os

import pytest

import centermanager.database.encryption_migration as migration


def _previous_artifacts(directory):
    return list(directory.glob(".*.previous-*"))


def test_candidate_install_failure_restores_database_and_sidecars(tmp_path, monkeypatch):
    database = tmp_path / "center.db"
    candidate = tmp_path / ".center.db.encrypted-test.tmp"
    wal = tmp_path / "center.db-wal"
    shm = tmp_path / "center.db-shm"

    database.write_bytes(b"old-database")
    candidate.write_bytes(b"new-encrypted-database")
    wal.write_bytes(b"old-wal")
    shm.write_bytes(b"old-shm")

    real_replace = os.replace

    def fail_candidate_install(src, dst):
        src_path = migration.Path(src)
        dst_path = migration.Path(dst)
        if src_path == candidate and dst_path == database:
            raise OSError("injected encrypted DB install failure")
        return real_replace(src, dst)

    monkeypatch.setattr(migration.os, "replace", fail_candidate_install)
    monkeypatch.setattr(
        migration,
        "_validate_encrypted_database",
        lambda path, key: None,
    )

    with pytest.raises(OSError, match="install failure"):
        migration._promote_encrypted_database(candidate, database, b"k" * 32)

    assert database.read_bytes() == b"old-database"
    assert wal.read_bytes() == b"old-wal"
    assert shm.read_bytes() == b"old-shm"
    assert candidate.read_bytes() == b"new-encrypted-database"
    assert _previous_artifacts(tmp_path) == []


def test_installed_validation_failure_rolls_every_artifact_back(tmp_path, monkeypatch):
    database = tmp_path / "center.db"
    candidate = tmp_path / ".center.db.encrypted-test.tmp"
    wal = tmp_path / "center.db-wal"
    shm = tmp_path / "center.db-shm"

    database.write_bytes(b"old-database")
    candidate.write_bytes(b"new-encrypted-database")
    wal.write_bytes(b"old-wal")
    shm.write_bytes(b"old-shm")

    def reject_installed(path, key):
        raise migration.DatabaseEncryptionMigrationError(
            "injected installed validation failure"
        )

    monkeypatch.setattr(migration, "_validate_encrypted_database", reject_installed)

    with pytest.raises(
        migration.DatabaseEncryptionMigrationError,
        match="installed validation failure",
    ):
        migration._promote_encrypted_database(candidate, database, b"k" * 32)

    assert database.read_bytes() == b"old-database"
    assert wal.read_bytes() == b"old-wal"
    assert shm.read_bytes() == b"old-shm"
    assert not candidate.exists()
    assert _previous_artifacts(tmp_path) == []
