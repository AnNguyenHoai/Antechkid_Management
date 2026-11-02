"""E1C-02 authority isolation tests; SQLite is single-client test-only.

Real PostgreSQL multi-process contention and production-equivalent remote denial
remain independent staging release gates.
"""
import hashlib
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from centermanager.coordinator.authority import (
    Coordinator, CoordinatorError, Candidate, Authority, Receipt, Audit, Outbox,
)
from centermanager.coordinator.storage import LocalCandidateStore


@pytest.fixture
def coordinator(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'authority.db'}")
    instance = Coordinator(engine, lease_seconds=60)
    instance.create_schema_for_tests()
    instance.bootstrap("repo", "0" * 64)
    yield instance
    engine.dispose()


def grant(coordinator):
    return coordinator.command("repo", "alice", "grant-1", "acquire",
                               expected_revision=0, session_id="session-a")


def candidate(coordinator):
    coordinator.register_candidate("repo", "alice", "candidate-1", "b" * 64,
                                   1, "synthetic-identity", verified=True)


def test_grant_lease_is_unique_and_idempotent(coordinator):
    first = grant(coordinator)
    assert first["epoch"] == 1 and first["revision"] == 1
    assert grant(coordinator) == first
    with pytest.raises(CoordinatorError, match="LEASE_HELD"):
        coordinator.command("repo", "bob", "grant-b", "acquire",
                            expected_revision=1, session_id="session-b")
    with pytest.raises(CoordinatorError, match="IDEMPOTENCY_CONFLICT"):
        coordinator.command("repo", "alice", "grant-1", "acquire",
                            expected_revision=0, session_id="different")


def test_publish_requires_verified_candidate_and_exact_owner(coordinator):
    granted = grant(coordinator)
    candidate(coordinator)
    with pytest.raises(CoordinatorError, match="STALE_SESSION"):
        coordinator.command("repo", "bob", "pub-b", "publish", epoch=1,
                            session_id="session-a", expected_revision=1,
                            expected_accepted_sha="0" * 64, candidate_id="candidate-1")
    accepted = coordinator.command(
        "repo", "alice", "pub-a", "publish", epoch=1,
        session_id="session-a", expected_revision=1,
        expected_accepted_sha="0" * 64, candidate_id="candidate-1"
    )
    assert accepted["accepted_sha"] == "b" * 64
    assert coordinator.state("repo")["generation"] == 1
    assert coordinator.get_receipt("repo", "alice", "pub-a") == accepted
    with Session(coordinator.engine) as session:
        assert len(session.execute(select(Outbox)).scalars().all()) == 1
        assert len(session.execute(select(Audit)).scalars().all()) == 2
    # The same exact accepted publish is stable across lost HTTP acknowledgements.
    assert coordinator.command("repo", "alice", "pub-a", "publish", epoch=1,
                               session_id="session-a", expected_revision=1,
                               expected_accepted_sha="0" * 64, candidate_id="candidate-1") == accepted


def test_revoke_fences_old_owner_and_requires_exact_target(coordinator):
    grant(coordinator)
    with pytest.raises(CoordinatorError, match="REVISION_CONFLICT"):
        coordinator.command("repo", "admin", "rev-bad", "revoke",
                            admin_authorized=True, expected_revision=1,
                            expected_epoch=1, target_session_id="other")
    revoked = coordinator.command("repo", "admin", "rev-1", "revoke",
                                   admin_authorized=True, expected_revision=1,
                                   expected_epoch=1, target_session_id="session-a")
    assert revoked["epoch"] == 2 and revoked["revision"] == 2
    with pytest.raises(CoordinatorError, match="STALE_SESSION"):
        coordinator.command("repo", "alice", "renew-old", "renew",
                            session_id="session-a", epoch=1, expected_revision=2)
    second = coordinator.command("repo", "bob", "grant-2", "acquire",
                                 session_id="session-b", expected_revision=2)
    assert second["epoch"] == 3
    with pytest.raises(CoordinatorError, match="REVISION_CONFLICT"):
        coordinator.command("repo", "admin", "revoke-old", "revoke",
                            admin_authorized=True, expected_revision=2,
                            expected_epoch=2, target_session_id="session-a")


def test_release_and_revision_fences(coordinator):
    grant(coordinator)
    with pytest.raises(CoordinatorError, match="REVISION_CONFLICT"):
        coordinator.command("repo", "alice", "renew-wrong", "renew",
                            session_id="session-a", epoch=1, expected_revision=0)
    updated = coordinator.command("repo", "alice", "renew-ok", "renew",
                                   session_id="session-a", epoch=1, expected_revision=1)
    assert updated["revision"] == 2
    coordinator.command("repo", "alice", "release", "release",
                        session_id="session-a", epoch=1, expected_revision=2)
    assert coordinator.state("repo")["owner_session"] is None


def test_invalid_candidate_does_not_move_pointer(coordinator):
    grant(coordinator)
    coordinator.register_candidate("repo", "alice", "unverified", "c" * 64, 1,
                                   "synthetic", verified=False)
    with pytest.raises(CoordinatorError, match="INVALID_CANDIDATE"):
        coordinator.command("repo", "alice", "publish-unverified", "publish",
                            session_id="session-a", epoch=1, expected_revision=1,
                            expected_accepted_sha="0" * 64, candidate_id="unverified")
    assert coordinator.state("repo")["revision"] == 1
    assert coordinator.get_receipt("repo", "alice", "publish-unverified") is None


def test_immutable_store_verifies_bytes_and_scope(tmp_path):
    storage = LocalCandidateStore(tmp_path / "candidates")
    data = b"synthetic ciphertext"
    digest = hashlib.sha256(data).hexdigest()
    assert storage.put("repo", data, digest) == digest
    assert storage.verify("repo", digest)
    assert not storage.verify("different-repo", digest)
    with pytest.raises(CoordinatorError, match="CANDIDATE_HASH_MISMATCH"):
        storage.put("repo", b"modified", digest)
