import json

import pytest

import scripts.migrate_production_repository_to_sqlcipher as migration_cli
from centermanager.database.artifact_identity import (
    DatabaseArtifactIdentityError,
    build_identity_document,
    identity_manifest_path,
    write_identity_document,
)


KEY = b"k" * 32


def _payload(manifest):
    return json.loads(manifest.read_text(encoding="utf-8"))["payload"]


def test_migration_rotates_authenticated_existing_identity(tmp_path):
    db = tmp_path / "center.db"
    db.write_bytes(b"legacy-plaintext-bytes")
    manifest = identity_manifest_path(db)
    predecessor = build_identity_document(
        db,
        KEY,
        database_id="11111111-1111-1111-1111-111111111111",
        generation=7,
    )
    write_identity_document(manifest, predecessor)

    # Model the in-place plaintext -> ciphertext mutation that occurs immediately
    # before the migration identity is written.
    db.write_bytes(b"sqlcipher-bytes")
    path, rotated = migration_cli._write_migrated_identity(db, KEY)

    assert path == manifest
    assert rotated is True
    payload = _payload(manifest)
    assert payload["database_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["generation"] == 8
    assert payload["sha256"] != predecessor["payload"]["sha256"]


def test_migration_creates_first_identity_when_sidecar_absent(tmp_path):
    db = tmp_path / "center.db"
    db.write_bytes(b"sqlcipher-bytes")

    manifest, rotated = migration_cli._write_migrated_identity(db, KEY)

    assert rotated is False
    assert manifest.is_file()
    assert _payload(manifest)["generation"] == 1


def test_migration_rejects_unauthenticated_existing_identity_without_overwrite(tmp_path):
    db = tmp_path / "center.db"
    db.write_bytes(b"sqlcipher-bytes")
    manifest = identity_manifest_path(db)
    original = '{"payload":{},"hmac_sha256":"forged"}\n'
    manifest.write_text(original, encoding="utf-8")

    with pytest.raises(DatabaseArtifactIdentityError):
        migration_cli._write_migrated_identity(db, KEY)

    assert manifest.read_text(encoding="utf-8") == original
