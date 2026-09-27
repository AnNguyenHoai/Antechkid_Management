# -*- coding: utf-8 -*-
import json
from pathlib import Path

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


class _Layout:
    service_name = "AnTechKidsData"
    database_path = Path("center.db")
    key_bundle_path = Path("key.dpapi")
    metadata_dir = Path("metadata")
    backup_dir = Path("backup")


class _Backend:
    def __init__(self):
        self.labels = []
        self.layout = _Layout()

    def health(self):
        return {"service": "AnTechKidsData", "protocol_version": PROTOCOL_VERSION}

    def validate_database(self):
        return {"valid": True, "database_sha256": "a" * 64}

    def create_backup(self, label):
        self.labels.append(label)
        return {"backup_id": "backup-1", "database_sha256": "b" * 64}


class _Domain:
    def __init__(self):
        self.auth = []
        self.tokens = []

    def authenticate(self, username, password, sid):
        self.auth.append((username, password, sid))
        return {"session_token": "token-1", "username": username}

    def logout(self, token, sid):
        self.tokens.append(("logout", token, sid))
        return {"logged_out": True}

    def list_students(self, token, sid):
        self.tokens.append(("list", token, sid))
        return {"students": [{"id": 1, "student_code": "HS001", "full_name": "A"}]}

    def create_student(self, token, sid, payload):
        self.tokens.append(("create", token, sid))
        return {"student": {"id": 2, "student_code": "HS002", **dict(payload)}}

    def _authorized_user(self, token, sid, *capabilities):
        self.tokens.append(("authorize", token, sid, tuple(c.value for c in capabilities)))
        return object()


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
    broker = ProtectedDataBroker(_Backend(), _Domain())
    request = BrokerRequest("req", ProtectedDataOperation.HEALTH, {})
    with pytest.raises(ProtectedDataBrokerError, match="caller identity"):
        broker.dispatch(request, CallerIdentity(sid=""))


def test_broker_authenticates_and_routes_student_domain_operations():
    backend = _Backend()
    domain = _Domain()
    broker = ProtectedDataBroker(backend, domain)
    caller = CallerIdentity(sid="S-1-5-21-test", account="TEST\\employee")

    auth = broker.dispatch(
        BrokerRequest(
            "a",
            ProtectedDataOperation.AUTHENTICATE,
            {"username": "employee", "password": "secret"},
        ),
        caller,
    )
    assert auth["session_token"] == "token-1"
    assert domain.auth == [("employee", "secret", caller.sid)]

    listed = broker.dispatch(
        BrokerRequest(
            "l", ProtectedDataOperation.STUDENT_LIST, {"session_token": "token-1"}
        ),
        caller,
    )
    assert listed["students"][0]["student_code"] == "HS001"

    created = broker.dispatch(
        BrokerRequest(
            "c",
            ProtectedDataOperation.STUDENT_CREATE,
            {"session_token": "token-1", "student": {"full_name": "New Student"}},
        ),
        caller,
    )
    assert created["student"]["full_name"] == "New Student"
    assert all(entry[2] == caller.sid for entry in domain.tokens)


def test_backup_requires_service_authenticated_capability():
    backend = _Backend()
    domain = _Domain()
    broker = ProtectedDataBroker(backend, domain)
    caller = CallerIdentity(sid="S-1-5-21-test")

    result = broker.dispatch(
        BrokerRequest(
            "b",
            ProtectedDataOperation.CREATE_BACKUP,
            {"session_token": "token-1", "label": "manual_1"},
        ),
        caller,
    )
    assert result["backup_id"] == "backup-1"
    assert backend.labels == ["manual_1"]
    assert any(entry[0] == "authorize" for entry in domain.tokens)


def test_response_never_adds_key_field_implicitly():
    raw = encode_response("req", result={"valid": True})
    response = json.loads(raw.decode("utf-8"))
    assert response["ok"] is True
    assert "key" not in response
    assert "key" not in response["result"]
