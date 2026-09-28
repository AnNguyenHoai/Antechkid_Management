import json
import os
from types import SimpleNamespace

import pytest

import centermanager.database.artifact_identity as identity
import centermanager.database.artifact_security as artifact_security


KEY = b"k" * 32
DATABASE_ID = "70da565e-4940-4fda-9f65-3b037b80bd24"


def _configure_local_state(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(
        identity,
        "get_paths",
        lambda: SimpleNamespace(config_dir=config_dir),
    )
    return config_dir


def _publish_manifest(database, *, database_id, generation):
    document = identity.build_identity_document(
        database,
        KEY,
        database_id=database_id,
        generation=generation,
    )
    identity.write_identity_document(identity.identity_manifest_path(database), document)


def test_valid_signed_identity_is_pinned_on_first_trust(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    database = tmp_path / "center.db"
    database.write_bytes(b"encrypted-artifact-v1")
    _publish_manifest(database, database_id=DATABASE_ID, generation=3)

    result = identity.validate_and_pin_identity(database, KEY)

    assert result.database_id == DATABASE_ID
    assert result.generation == 3
    assert identity.local_identity_state_path().is_file()


def test_database_byte_tamper_is_rejected(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    database = tmp_path / "center.db"
    database.write_bytes(b"encrypted-artifact-v1")
    _publish_manifest(database, database_id=DATABASE_ID, generation=1)
    database.write_bytes(b"tampered-artifact")

    with pytest.raises(
        identity.DatabaseArtifactIdentityError,
        match="do not match the signed identity",
    ):
        identity.validate_and_pin_identity(database, KEY)


def test_manifest_hmac_tamper_is_rejected(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    database = tmp_path / "center.db"
    database.write_bytes(b"encrypted-artifact-v1")
    manifest = identity.identity_manifest_path(database)
    _publish_manifest(database, database_id=DATABASE_ID, generation=1)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["payload"]["generation"] = 9
    manifest.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(
        identity.DatabaseArtifactIdentityError,
        match="authentication failed",
    ):
        identity.validate_and_pin_identity(database, KEY)


def test_foreign_database_id_is_rejected_after_pin(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    database = tmp_path / "center.db"
    database.write_bytes(b"workspace-database")
    _publish_manifest(database, database_id=DATABASE_ID, generation=4)
    identity.validate_and_pin_identity(database, KEY)

    _publish_manifest(
        database,
        database_id="9cb790f1-b901-479b-888b-d9b555f92daa",
        generation=5,
    )

    with pytest.raises(
        identity.DatabaseArtifactIdentityError,
        match="does not match the locally pinned",
    ):
        identity.validate_and_pin_identity(database, KEY)


def test_generation_rollback_is_rejected_after_higher_generation_seen(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    database = tmp_path / "center.db"
    database.write_bytes(b"workspace-database")
    _publish_manifest(database, database_id=DATABASE_ID, generation=8)
    identity.validate_and_pin_identity(database, KEY)

    _publish_manifest(database, database_id=DATABASE_ID, generation=7)

    with pytest.raises(
        identity.DatabaseArtifactIdentityError,
        match="older than the locally trusted generation",
    ):
        identity.validate_and_pin_identity(database, KEY)


def test_identity_install_failure_restores_previous_database_and_manifest(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    repo_db = tmp_path / "center.db"
    source_tmp = tmp_path / ".center.db.publish-candidate.tmp"
    repo_db.write_bytes(b"old-encrypted-database")
    source_tmp.write_bytes(b"new-encrypted-database")
    _publish_manifest(repo_db, database_id=DATABASE_ID, generation=3)
    old_manifest = identity.identity_manifest_path(repo_db).read_bytes()

    # Pin the current pair before publication. Crypto validity is orthogonal to
    # this unit test; exact byte binding and identity validation remain real.
    identity.validate_and_pin_identity(repo_db, KEY)
    monkeypatch.setattr(
        artifact_security,
        "validate_database_artifact",
        lambda path, **kwargs: None,
    )

    manifest = identity.identity_manifest_path(repo_db)
    real_replace = os.replace

    def fail_identity_install(src, dst):
        src_path = artifact_security.Path(src)
        dst_path = artifact_security.Path(dst)
        if (
            dst_path == manifest
            and src_path.name.startswith(f".{manifest.name}.publish-")
        ):
            raise OSError("injected identity install failure")
        return real_replace(src, dst)

    monkeypatch.setattr(artifact_security.os, "replace", fail_identity_install)

    with pytest.raises(OSError, match="identity install failure"):
        artifact_security._publish_encrypted_repository_pair(source_tmp, repo_db, KEY)

    assert repo_db.read_bytes() == b"old-encrypted-database"
    assert manifest.read_bytes() == old_manifest
    assert not list(tmp_path.glob(".*.previous-*"))


def test_successful_publication_preserves_database_id_and_increments_generation(
    tmp_path, monkeypatch
):
    _configure_local_state(tmp_path, monkeypatch)
    repo_db = tmp_path / "center.db"
    source_tmp = tmp_path / ".center.db.publish-candidate.tmp"
    repo_db.write_bytes(b"old-encrypted-database")
    source_tmp.write_bytes(b"new-encrypted-database")
    _publish_manifest(repo_db, database_id=DATABASE_ID, generation=5)
    identity.validate_and_pin_identity(repo_db, KEY)
    monkeypatch.setattr(
        artifact_security,
        "validate_database_artifact",
        lambda path, **kwargs: None,
    )

    artifact_security._publish_encrypted_repository_pair(source_tmp, repo_db, KEY)

    published = identity.validate_and_pin_identity(repo_db, KEY)
    assert repo_db.read_bytes() == b"new-encrypted-database"
    assert published.database_id == DATABASE_ID
    assert published.generation == 6
    assert not list(tmp_path.glob(".*.previous-*"))
