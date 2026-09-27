# -*- coding: utf-8 -*-
import json

import pytest

from centermanager.platform.protected_data_service.broker import (
    MAX_REQUEST_BYTES,
    BrokerRequest,
    CallerIdentity,
    ProtectedDataBroker,
    ProtectedDataBrokerError,
    ProtectedDataProtocolError,
    decode_request,
    encode_response,
)
from centermanager.platform.protected_data_service.protocol import (
    PROTOCOL_VERSION,
    ProtectedDataOperation,
)


class _Backend:
    def __init__(self):
        self.labels = []

    def health(self):
        return {"service": "AnTechKidsData", "protocol_version": PROTOCOL_VERSION}

    def validate_database(self):
        return {"valid": True, "database_sha256": "a" * 64}

    def create_backup(self, label):
        self.labels.append(label)
        return {"backup_id": "backup-1", "database_sha256": "b" * 64}


def _encoded(operation="health", *, request_id="req-1", payload=None, version=PROTOCOL_VERSION):
    return json.dumps({
        "version": version,
        "request_id": request_id,
        "operation": operation,
        "payload": payload or {},
    }).encode("utf-8")


def test_decode_request_accepts_versioned_safe_operation():
    request = decode_request(_encoded("validate_database"))
    assert request.request_id == "req-1"
    assert request.operation is ProtectedDataOperation.VALIDATE_DATABASE


def test_decode_request_rejects_unknown_operation_and_raw_sql():
    with pytest.raises(ProtectedDataProtocolError, match="Unsupported"):
        decode_request(_encoded("execute_sql", payload={"sql": "DELETE FROM students"}))


def test_decode_request_rejects_wrong_version_and_oversize():
    with pytest.raises(ProtectedDataProtocolError, match="version"):
        decode_request(_encoded(version=PROTOCOL_VERSION + 1))
    with pytest.raises(ProtectedDataProtocolError, match="size"):
        decode_request(b"x" * (MAX_REQUEST_BYTES + 1))


def test_broker_requires_os_authenticated_caller_identity():
    broker = ProtectedDataBroker(_Backend())
    request = BrokerRequest("req", ProtectedDataOperation.HEALTH, {})
    with pytest.raises(ProtectedDataBrokerError, match="caller identity"):
        broker.dispatch(request, CallerIdentity(sid=""))


def test_broker_dispatches_only_operation_oriented_contract():
    backend = _Backend()
    broker = ProtectedDataBroker(backend)
    caller = CallerIdentity(sid="S-1-5-21-test", account="TEST\\employee")

    assert broker.dispatch(
        BrokerRequest("h", ProtectedDataOperation.HEALTH, {}), caller
    )["service"] == "AnTechKidsData"
    assert broker.dispatch(
        BrokerRequest("v", ProtectedDataOperation.VALIDATE_DATABASE, {}), caller
    )["valid"] is True
    result = broker.dispatch(
        BrokerRequest("b", ProtectedDataOperation.CREATE_BACKUP, {"label": "manual_1"}), caller
    )
    assert result["backup_id"] == "backup-1"
    assert backend.labels == ["manual_1"]


def test_response_never_adds_key_field_implicitly():
    raw = encode_response("req", result={"valid": True})
    response = json.loads(raw.decode("utf-8"))
    assert response["ok"] is True
    assert "key" not in response
    assert "key" not in response["result"]
