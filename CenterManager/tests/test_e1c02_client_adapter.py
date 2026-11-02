"""E1C Phase 4 client is strictly inactive unless explicitly configured."""
import io
import json
from urllib.error import URLError
import pytest
from centermanager.coordinator.client_adapter import (
    CoordinatorClientAdapter, CoordinatorProtocolGate, CoordinatorTransportError,
)


class Response:
    def __init__(self, value):
        self.buffer = io.BytesIO(json.dumps(value).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.buffer.read()


def fixture_transport(*, lose_push_ack=False, reject=False):
    calls = []
    receipt = {"status": "ACCEPTED", "action": "publish", "accepted_sha": "b"*64,
               "epoch": 1, "revision": 3}
    def transport(req, timeout):
        assert req.full_url.startswith("https://coordinator.test/v1/repositories/test/")
        assert req.headers["Authorization"] == "Bearer synthetic"
        assert req.headers["X-client-protocol"] == "e1c/1"
        calls.append((req.get_method(), req.full_url))
        if req.get_method() == "POST":
            if reject:
                raise URLError("connection unavailable")
            if lose_push_ack:
                raise URLError("ack missing after accepted publication")
        return Response(receipt)
    return transport, calls


def client(transport):
    return CoordinatorClientAdapter("https://coordinator.test", "test",
                                    lambda: "synthetic", transport=transport)


def publish(adapter):
    return adapter.publish_candidate(
        request_id="pub-1", session_id="session-a", epoch=1, revision=2,
        previous_sha="a"*64, candidate_id="candidate-1", intended_sha="b"*64,
    )


def test_https_required_and_gate_denies_legacy_fallback():
    with pytest.raises(CoordinatorTransportError, match="HTTPS_COORDINATOR_REQUIRED"):
        CoordinatorClientAdapter("http://coordinator.test", "test", lambda: "secret")
    with pytest.raises(CoordinatorTransportError, match="COORDINATOR_NOT_ENABLED"):
        CoordinatorProtocolGate().require_write()
    with pytest.raises(CoordinatorTransportError, match="INCOMPATIBLE_PROTOCOL"):
        CoordinatorProtocolGate(enabled=True, protocol="legacy").require_write()
    assert CoordinatorProtocolGate(enabled=True, protocol="e1c/1").require_write()
    with pytest.raises(CoordinatorTransportError, match="LEGACY_GIT_PUBLICATION_FORBIDDEN"):
        CoordinatorProtocolGate(enabled=True, protocol="e1c/1").forbidden_git_fallback()


def test_verified_receipt_required_even_after_successful_post():
    transport, calls = fixture_transport()
    result = publish(client(transport))
    assert result.accepted_sha == "b"*64
    assert [method for method, _ in calls] == ["POST", "GET"]


def test_lost_ack_queries_receipt_without_blind_second_post():
    transport, calls = fixture_transport(lose_push_ack=True)
    result = publish(client(transport))
    assert result.revision == 3
    assert [method for method, _ in calls] == ["POST", "GET"]


def test_unknown_receipt_cannot_be_called_accepted():
    calls = []
    def transport(req, timeout):
        calls.append(req.get_method())
        if req.get_method() == "POST":
            raise URLError("lost ack")
        raise URLError("remote read unavailable")
    with pytest.raises(CoordinatorTransportError, match="UNKNOWN_OUTCOME"):
        publish(client(transport))
    assert calls == ["POST", "GET"]


def test_receipt_mismatch_is_hard_failure():
    def transport(req, timeout):
        return Response({"status": "ACCEPTED", "action": "publish",
                         "accepted_sha": "wrong", "revision": 3, "epoch": 1})
    with pytest.raises(CoordinatorTransportError, match="RECEIPT_MISMATCH"):
        publish(client(transport))
