import json
from types import SimpleNamespace

import pytest

import centermanager.database.artifact_identity as identity


KEY = b"k" * 32


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
    database_id = "70da565e-4940-4fda-9f65-3b037b80bd24"
    _publish_manifest(database, database_id=database_id, generation=3)

    result = identity.validate_and_pin_identity(database, KEY)

    assert result.database_id == database_id
    assert result.generation == 3
    assert identity.local_identity_state_path().is_file()


def test_database_byte_tamper_is_rejected(tmp_path, monkeypatch):
    _configure_local_state(tmp_path, monkeypatch)
    database = tmp_path / "center.db"
    database.write_bytes(b"encrypted-artifact-v1")
    _publish_manifest(
        database,
        database_id="70da565e-4940-4fda-9f65-3b037b80bd24",
        generation=1,
    )
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
    _publish_manifest(
        database,
        database_id="70da565e-4940-4fda-9f65-3b037b80bd24",
        generation=1,
    )
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
    _publish_manifest(
        database,
        database_id="70da565e-4940-4fda-9f65-3b037b80bd24",
        generation=4,
    )
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
    database_id = "70da565e-4940-4fda-9f65-3b037b80bd24"
    _publish_manifest(database, database_id=database_id, generation=8)
    identity.validate_and_pin_identity(database, KEY)

    _publish_manifest(database, database_id=database_id, generation=7)

    with pytest.raises(
        identity.DatabaseArtifactIdentityError,
        match="older than the locally trusted generation",
    ):
        identity.validate_and_pin_identity(database, KEY)
