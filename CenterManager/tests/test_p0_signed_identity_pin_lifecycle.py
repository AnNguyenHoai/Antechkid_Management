"""SEC-05 regression: signed database identity and local pin are distinct phases.

This test operates on real HMAC-signed artifact bytes. Integration with
SQLCipher and Git remote publication is separately required before release.
"""
import hashlib
import json
import uuid

import pytest

from centermanager.database import artifact_identity as identity


def test_candidate_validation_cannot_advance_local_pin(tmp_path, monkeypatch):
    key = b"test-only-workspace-key"
    candidate = tmp_path / "center.db"
    candidate.write_bytes(b"candidate-encrypted-payload")
    database_id = str(uuid.uuid4())
    state_path = tmp_path / "authoritative_database_identity.json"
    monkeypatch.setattr(identity, "local_identity_state_path", lambda: state_path)

    signed = identity.build_identity_document(
        candidate, key, database_id=database_id, generation=1,
    )
    identity.write_identity_document(identity.identity_manifest_path(candidate), signed)

    assert identity.validate_identity(candidate, key).generation == 1
    assert not state_path.exists()

    assert identity.pin_validated_identity(candidate, key).generation == 1
    initial_state = state_path.read_bytes()

    candidate.write_bytes(b"next-candidate-encrypted-payload")
    signed = identity.build_identity_document(
        candidate, key, database_id=database_id, generation=2,
    )
    identity.write_identity_document(identity.identity_manifest_path(candidate), signed)
    assert identity.validate_identity(candidate, key).generation == 2
    assert state_path.read_bytes() == initial_state, "validation must never advance pin"

    candidate.write_bytes(b"tampered payload")
    with pytest.raises(identity.DatabaseArtifactIdentityError, match="do not match"):
        identity.validate_identity(candidate, key)
    assert state_path.read_bytes() == initial_state


def test_successful_pin_advances_floor_and_blocks_rollback(tmp_path, monkeypatch):
    key = b"test-only-workspace-key"
    candidate = tmp_path / "center.db"
    candidate.write_bytes(b"v1")
    database_id = str(uuid.uuid4())
    state_path = tmp_path / "pin.json"
    monkeypatch.setattr(identity, "local_identity_state_path", lambda: state_path)
    v1 = identity.build_identity_document(candidate, key, database_id=database_id, generation=1)
    identity.write_identity_document(identity.identity_manifest_path(candidate), v1)
    identity.pin_validated_identity(candidate, key)

    candidate.write_bytes(b"v2")
    v2 = identity.build_identity_document(candidate, key, database_id=database_id, generation=2)
    identity.write_identity_document(identity.identity_manifest_path(candidate), v2)
    identity.validate_identity(candidate, key)
    assert json.loads(state_path.read_text())["payload"]["highest_generation"] == 1
    identity.pin_validated_identity(candidate, key)
    assert json.loads(state_path.read_text())["payload"]["highest_generation"] == 2

    candidate.write_bytes(b"v1")
    identity.write_identity_document(identity.identity_manifest_path(candidate), v1)
    with pytest.raises(identity.DatabaseArtifactIdentityError, match="older"):
        identity.validate_identity(candidate, key)
