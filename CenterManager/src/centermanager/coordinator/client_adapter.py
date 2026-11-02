"""Inactive-by-default Windows coordinator transport preparation.

This adapter never falls back to Git, cannot activate production sync, and treats
uncertain HTTP acknowledgement as UNKNOWN until receipt reconciliation succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import request, error, parse

PROTOCOL = "e1c/1"


class CoordinatorTransportError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AcceptedReceipt:
    request_id: str
    revision: int
    epoch: int
    accepted_sha: str


class CoordinatorClientAdapter:
    """Transport-only, not a drop-in replacement for legacy publish_only.

    Callers must preserve E1B journal and local SQLCipher snapshots separately.
    """
    def __init__(self, base_url: str, repository_id: str, token_supplier,
                 *, timeout=10, transport=None):
        parsed = parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise CoordinatorTransportError("HTTPS_COORDINATOR_REQUIRED")
        if not repository_id or "/" in repository_id or not callable(token_supplier):
            raise CoordinatorTransportError("INVALID_CLIENT_CONFIGURATION")
        self.base = base_url.rstrip("/")
        self.repository = parse.quote(repository_id, safe="")
        self.token_supplier = token_supplier
        self.timeout = timeout
        self._transport = transport or request.urlopen

    def _call(self, method, path, payload=None):
        token = self.token_supplier()
        if not isinstance(token, str) or not token:
            raise CoordinatorTransportError("AUTHENTICATION_UNAVAILABLE")
        data = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
        req = request.Request(
            self.base + "/v1/repositories/" + self.repository + path,
            data=data, method=method,
            headers={"Authorization": "Bearer " + token,
                     "X-Client-Protocol": PROTOCOL,
                     "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        try:
            with self._transport(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result, dict):
                    raise CoordinatorTransportError("INVALID_COORDINATOR_RESPONSE")
                return result
        except error.HTTPError as exc:
            raise CoordinatorTransportError("COORDINATOR_REJECTED") from exc
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise CoordinatorTransportError("UNKNOWN_OUTCOME") from exc

    def state(self):
        return self._call("GET", "/state")

    def authority_command(self, *, request_id, action, params):
        if action not in ("acquire", "renew", "release"):
            raise CoordinatorTransportError("UNSUPPORTED_SESSION_COMMAND")
        if not request_id or not isinstance(params, dict):
            raise CoordinatorTransportError("INVALID_SESSION_COMMAND")
        return self._call("POST", "/commands", {
            "request_id": request_id, "action": action, "params": params
        })

    def reconcile_command(self, request_id, action):
        result = self._call("GET", "/requests/" + parse.quote(request_id, safe=""))
        if result.get("status") != "ACCEPTED" or result.get("action") != action:
            raise CoordinatorTransportError("RECEIPT_MISMATCH")
        return result

    def reconcile(self, request_id: str, *, expected_sha: str) -> AcceptedReceipt:
        if not request_id or not expected_sha:
            raise CoordinatorTransportError("INVALID_RECEIPT_QUERY")
        result = self._call("GET", "/requests/" + parse.quote(request_id, safe=""))
        if (result.get("status") != "ACCEPTED" or result.get("action") != "publish"
                or result.get("accepted_sha") != expected_sha
                or type(result.get("revision")) is not int
                or type(result.get("epoch")) is not int):
            raise CoordinatorTransportError("RECEIPT_MISMATCH")
        return AcceptedReceipt(request_id, result["revision"], result["epoch"],
                               result["accepted_sha"])

    def publish_candidate(self, *, request_id, session_id, epoch, revision,
                          previous_sha, candidate_id, intended_sha):
        """Send once, then require exact accepted receipt; never retry blindly."""
        if not all((request_id, session_id, candidate_id, intended_sha)):
            raise CoordinatorTransportError("INVALID_PUBLICATION")
        try:
            result = self._call("POST", "/commands", {
                "request_id": request_id, "action": "publish",
                "params": {"session_id": session_id, "epoch": epoch,
                           "expected_revision": revision,
                           "expected_accepted_sha": previous_sha,
                           "candidate_id": candidate_id}
            })
        except CoordinatorTransportError as exc:
            if exc.code == "UNKNOWN_OUTCOME":
                # A lost acknowledgement is not evidence of acceptance or failure.
                return self.reconcile(request_id, expected_sha=intended_sha)
            raise
        if result.get("status") != "ACCEPTED" or result.get("accepted_sha") != intended_sha:
            raise CoordinatorTransportError("RECEIPT_MISMATCH")
        # An HTTP response must match the stored server receipt before local cleanup.
        return self.reconcile(request_id, expected_sha=intended_sha)


class CoordinatorProtocolGate:
    """An explicit opt-in boundary. No implicit legacy Git fallback."""
    def __init__(self, *, enabled=False, protocol=None):
        self.enabled = bool(enabled)
        self.protocol = protocol

    def require_write(self):
        if not self.enabled:
            raise CoordinatorTransportError("COORDINATOR_NOT_ENABLED")
        if self.protocol != PROTOCOL:
            raise CoordinatorTransportError("INCOMPATIBLE_PROTOCOL")
        return True

    def forbidden_git_fallback(self):
        raise CoordinatorTransportError("LEGACY_GIT_PUBLICATION_FORBIDDEN")
