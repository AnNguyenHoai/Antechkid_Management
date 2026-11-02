"""Coordinator WRITE session and publication proof staging regression."""
import hashlib
import uuid

import pytest
from centermanager.coordinator.client_adapter import (
    CoordinatorProtocolGate, CoordinatorTransportError, AcceptedReceipt,
)
from centermanager.coordinator.write_session import CoordinatorWriteSession
from centermanager.coordinator.recovery import (
    verify_coordinator_publication, require_coordinator_journal_migration,
)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.receipts = {}
        self.lose_next_ack = False

    def authority_command(self, *, request_id, action, params):
        self.calls.append(("POST", action, request_id))
        if action == "acquire":
            value = {"status":"ACCEPTED", "action":action, "epoch":1,
                     "revision":1, "expires_at":"2030-01-01T00:00:00Z"}
        elif action == "renew":
            value = {"status":"ACCEPTED", "action":action, "epoch":1,
                     "revision":2, "expires_at":"2030-01-01T00:00:30Z"}
        else:
            value = {"status":"ACCEPTED", "action":action, "epoch":1,
                     "revision":3, "expires_at":None}
        self.receipts[request_id] = value
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise CoordinatorTransportError("UNKNOWN_OUTCOME")
        return value

    def reconcile_command(self, request_id, action):
        self.calls.append(("GET", action, request_id))
        return self.receipts[request_id]


def test_acquire_renew_release_does_not_touch_legacy_git():
    client = FakeClient()
    session = CoordinatorWriteSession(client, CoordinatorProtocolGate(enabled=True, protocol="e1c/1"))
    grant = session.acquire(0, session_id="a", request_id="a1")
    assert (grant.epoch, grant.revision, grant.session_id) == (1, 1, "a")
    renewed = session.renew(request_id="r1")
    assert renewed.revision == 2
    session.release(request_id="end")
    assert session.grant is None
    assert [x[1] for x in client.calls] == ["acquire", "renew", "release"]
    with pytest.raises(CoordinatorTransportError, match="LEGACY_GIT_PUBLICATION_FORBIDDEN"):
        session.reject_legacy_fallback()


def test_lost_ack_reconciles_once_without_second_mutation():
    client = FakeClient()
    client.lose_next_ack = True
    session = CoordinatorWriteSession(client, CoordinatorProtocolGate(enabled=True, protocol="e1c/1"))
    assert session.acquire(0, request_id="unique-1").revision == 1
    assert client.calls == [("POST", "acquire", "unique-1"),
                            ("GET", "acquire", "unique-1")]


def test_unknown_command_outcome_fails_closed():
    class Offline(FakeClient):
        def reconcile_command(self, request_id, action):
            raise CoordinatorTransportError("UNKNOWN_OUTCOME")
    session = CoordinatorWriteSession(Offline(), CoordinatorProtocolGate(enabled=True, protocol="e1c/1"))
    session.client.lose_next_ack = True
    with pytest.raises(CoordinatorTransportError, match="UNKNOWN_OUTCOME"):
        session.acquire(0)
    assert session.grant is None


def test_disabled_protocol_never_sends_command():
    client = FakeClient()
    session = CoordinatorWriteSession(client, CoordinatorProtocolGate())
    with pytest.raises(CoordinatorTransportError, match="COORDINATOR_NOT_ENABLED"):
        session.acquire(0)
    assert client.calls == []


def test_local_snapshot_and_server_receipt_both_required(tmp_path):
    snapshot = tmp_path / "snapshot.db"
    snapshot.write_bytes(b"encrypted-synthetic-db")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    class Verified:
        def reconcile(self, request_id, *, expected_sha):
            assert request_id == "publish-1" and expected_sha == digest
            return AcceptedReceipt(request_id, 5, 2, expected_sha)
    proof = verify_coordinator_publication(
        client=Verified(), request_id="publish-1",
        expected_candidate_sha=digest, local_snapshot=snapshot)
    assert (proof.accepted_revision, proof.epoch, proof.local_sha256) == (5, 2, digest)
    snapshot.write_bytes(b"modified")
    with pytest.raises(CoordinatorTransportError, match="LOCAL_SNAPSHOT_MISMATCH"):
        verify_coordinator_publication(
            client=Verified(), request_id="publish-1",
            expected_candidate_sha=digest, local_snapshot=snapshot)
    with pytest.raises(CoordinatorTransportError, match="COORDINATOR_JOURNAL_NOT_MIGRATED"):
        require_coordinator_journal_migration()
