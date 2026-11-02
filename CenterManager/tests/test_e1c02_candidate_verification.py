"""E1C Phase 2: adversarial candidate verification tests (isolated DB/keys)."""
import base64
import hashlib

import pytest
from sqlalchemy import create_engine
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from centermanager.coordinator.authority import Coordinator, CoordinatorError
from centermanager.coordinator.storage import LocalCandidateStore
from centermanager.coordinator.verification import (
    CandidateVerifier, TrustedRepository, canonical_manifest,
)


@pytest.fixture
def environment(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    coordinator = Coordinator(engine)
    coordinator.create_schema_for_tests()
    coordinator.bootstrap("repo", "0" * 64)
    store = LocalCandidateStore(tmp_path / "blobs")
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    verifier = CandidateVerifier(coordinator, store, {
        "repo": TrustedRepository(database_id="synthetic-db", signer_public_key=public)
    })
    payload = b"synthetic ciphertext bytes; never production data"
    digest = hashlib.sha256(payload).hexdigest()
    store.put("repo", payload, digest)
    manifest = {
        "protocol": "e1c-candidate-v1", "repository_id": "repo",
        "database_id": "synthetic-db", "generation": 1,
        "ciphertext_sha256": digest, "ciphertext_size": len(payload)
    }
    def sign(m):
        return base64.b64encode(private.sign(canonical_manifest(m))).decode()
    yield coordinator, verifier, manifest, sign, store
    engine.dispose()


def test_signed_exact_candidate_can_be_published(environment):
    authority, verifier, manifest, sign, store = environment
    accepted = verifier.verify_and_register("repo", "alice", "candidate-1", manifest, sign(manifest))
    assert accepted["status"] == "VERIFIED_CANDIDATE"
    grant = authority.command("repo", "alice", "grant", "acquire",
                              expected_revision=0, session_id="session")
    result = authority.command("repo", "alice", "pub", "publish",
                               session_id="session", epoch=grant["epoch"],
                               expected_revision=1, expected_accepted_sha="0"*64,
                               candidate_id="candidate-1")
    assert result["accepted_sha"] == manifest["ciphertext_sha256"]


@pytest.mark.parametrize("field,value,error", [
    ("database_id", "another-db", "DATABASE_IDENTITY_MISMATCH"),
    ("repository_id", "another-repo", "DATABASE_IDENTITY_MISMATCH"),
    ("generation", 0, "INVALID_MANIFEST"),
    ("ciphertext_sha256", "f"*64, "CANDIDATE_STORAGE_MISMATCH"),
    ("ciphertext_size", 12345, "CANDIDATE_SIZE_MISMATCH"),
])
def test_signed_wrong_identity_or_blob_never_verifies(environment, field, value, error):
    authority, verifier, manifest, sign, _ = environment
    altered = {**manifest, field: value}
    with pytest.raises(CoordinatorError, match=error):
        verifier.verify_and_register("repo", "alice", "candidate-1", altered, sign(altered))
    assert authority.state("repo")["accepted_sha"] == "0"*64


def test_modified_manifest_with_original_signature_is_rejected(environment):
    authority, verifier, manifest, sign, _ = environment
    signature = sign(manifest)
    modified = {**manifest, "generation": 9}
    with pytest.raises(CoordinatorError, match="INVALID_SIGNATURE"):
        verifier.verify_and_register("repo", "alice", "candidate-1", modified, signature)


def test_invalid_signer_and_unknown_repo_fail_closed(environment):
    authority, verifier, manifest, sign, _ = environment
    other = Ed25519PrivateKey.generate()
    false_signature = base64.b64encode(other.sign(canonical_manifest(manifest))).decode()
    with pytest.raises(CoordinatorError, match="INVALID_SIGNATURE"):
        verifier.verify_and_register("repo", "alice", "candidate-1", manifest, false_signature)
    with pytest.raises(CoordinatorError, match="UNKNOWN_TRUST_ROOT"):
        verifier.verify_and_register("unknown", "alice", "candidate-x", manifest, sign(manifest))


def test_unverified_upload_is_never_accepted(environment):
    authority, verifier, manifest, sign, _ = environment
    authority.register_candidate("repo", "alice", "unverified", manifest["ciphertext_sha256"],
                                 1, "synthetic-db", verified=False)
    grant = authority.command("repo", "alice", "grant", "acquire",
                              expected_revision=0, session_id="session")
    with pytest.raises(CoordinatorError, match="INVALID_CANDIDATE"):
        authority.command("repo", "alice", "pub", "publish",
                          session_id="session", epoch=grant["epoch"],
                          expected_revision=1, expected_accepted_sha="0"*64,
                          candidate_id="unverified")


def test_replay_after_generation_accepted_is_rejected(environment):
    authority, verifier, manifest, sign, _ = environment
    verifier.verify_and_register("repo", "alice", "first", manifest, sign(manifest))
    grant = authority.command("repo", "alice", "grant", "acquire",
                              expected_revision=0, session_id="session")
    authority.command("repo", "alice", "pub", "publish", session_id="session",
                      epoch=grant["epoch"], expected_revision=1,
                      expected_accepted_sha="0"*64, candidate_id="first")
    with pytest.raises(CoordinatorError, match="STALE_GENERATION"):
        verifier.verify_and_register("repo", "alice", "replay", manifest, sign(manifest))
