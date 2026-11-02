"""Coordinator-native WRITE session, separate from legacy Git collaboration.

No production activation. Every uncertain command is reconciled by request ID.
"""
from dataclasses import dataclass
import uuid

from .client_adapter import CoordinatorTransportError, CoordinatorProtocolGate


@dataclass(frozen=True)
class SessionGrant:
    session_id: str
    epoch: int
    revision: int
    expires_at: str


class CoordinatorWriteSession:
    def __init__(self, client, gate: CoordinatorProtocolGate):
        self.client = client
        self.gate = gate
        self.grant = None

    def _command(self, action, params, request_id=None):
        self.gate.require_write()
        identifier = request_id or str(uuid.uuid4())
        try:
            response = self.client.authority_command(
                request_id=identifier, action=action, params=params)
        except CoordinatorTransportError as exc:
            if exc.code != "UNKNOWN_OUTCOME":
                raise
            response = self.client.reconcile_command(identifier, action)
        if (response.get("status") != "ACCEPTED" or response.get("action") != action
                or type(response.get("revision")) is not int
                or type(response.get("epoch")) is not int):
            raise CoordinatorTransportError("INVALID_AUTHORITY_RECEIPT")
        return response

    def acquire(self, expected_revision, *, session_id=None, request_id=None):
        if self.grant is not None:
            raise CoordinatorTransportError("SESSION_ALREADY_ACTIVE")
        session_id = session_id or str(uuid.uuid4())
        response = self._command("acquire", {
            "expected_revision": expected_revision, "session_id": session_id
        }, request_id=request_id)
        if not isinstance(response.get("expires_at"), str) or not response["expires_at"]:
            raise CoordinatorTransportError("INVALID_AUTHORITY_RECEIPT")
        self.grant = SessionGrant(session_id, response["epoch"],
                                  response["revision"], response["expires_at"])
        return self.grant

    def renew(self, *, request_id=None):
        if self.grant is None:
            raise CoordinatorTransportError("NO_ACTIVE_SESSION")
        current = self.grant
        response = self._command("renew", {
            "session_id": current.session_id, "epoch": current.epoch,
            "expected_revision": current.revision
        }, request_id=request_id)
        if response["epoch"] != current.epoch or not response.get("expires_at"):
            raise CoordinatorTransportError("INVALID_AUTHORITY_RECEIPT")
        self.grant = SessionGrant(current.session_id, current.epoch,
                                  response["revision"], response["expires_at"])
        return self.grant

    def release(self, *, request_id=None):
        if self.grant is None:
            raise CoordinatorTransportError("NO_ACTIVE_SESSION")
        current = self.grant
        response = self._command("release", {
            "session_id": current.session_id, "epoch": current.epoch,
            "expected_revision": current.revision
        }, request_id=request_id)
        if response["epoch"] != current.epoch or response.get("expires_at") is not None:
            raise CoordinatorTransportError("INVALID_AUTHORITY_RECEIPT")
        self.grant = None
        return response

    def reject_legacy_fallback(self):
        self.gate.forbidden_git_fallback()
