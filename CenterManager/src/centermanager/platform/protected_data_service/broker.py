# -*- coding: utf-8 -*-
"""Operation-oriented broker for the protected Windows data service."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from centermanager.core.capabilities import Capability
from centermanager.database.artifact_security import validate_database_artifact
from centermanager.database.encryption import (
    DatabaseKeyStore,
    apply_sqlcipher_key,
    load_sqlcipher_driver,
)
from centermanager.security.protected_storage import (
    ProtectedStorageLayout,
    get_protected_storage_layout,
)

from .domain_gateway import ProtectedDomainError, ProtectedDomainGateway
from .protocol import PROTOCOL_VERSION, ProtectedDataOperation

MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")
_BACKUP_LABEL_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")


class ProtectedDataBrokerError(RuntimeError):
    pass


class ProtectedDataProtocolError(ProtectedDataBrokerError):
    pass


@dataclass(frozen=True)
class BrokerRequest:
    request_id: str
    operation: ProtectedDataOperation
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class CallerIdentity:
    sid: str
    account: str = ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_request(data: bytes) -> BrokerRequest:
    if not data or len(data) > MAX_REQUEST_BYTES:
        raise ProtectedDataProtocolError("Request is empty or exceeds the size limit.")
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtectedDataProtocolError("Request must be valid UTF-8 JSON.") from exc
    if not isinstance(message, dict):
        raise ProtectedDataProtocolError("Request envelope must be an object.")
    if message.get("version") != PROTOCOL_VERSION:
        raise ProtectedDataProtocolError("Unsupported protected-data protocol version.")
    request_id = str(message.get("request_id", ""))
    if not _REQUEST_ID_RE.fullmatch(request_id):
        raise ProtectedDataProtocolError("Invalid request_id.")
    try:
        operation = ProtectedDataOperation(str(message.get("operation", "")))
    except ValueError as exc:
        raise ProtectedDataProtocolError("Unsupported protected-data operation.") from exc
    payload = message.get("payload", {})
    if not isinstance(payload, dict):
        raise ProtectedDataProtocolError("Request payload must be an object.")
    return BrokerRequest(request_id=request_id, operation=operation, payload=payload)


def encode_response(
    request_id: str,
    *,
    result: Mapping[str, Any] | None = None,
    error: str | None = None,
) -> bytes:
    envelope: dict[str, Any] = {
        "version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": error is None,
    }
    if error is None:
        envelope["result"] = dict(result or {})
    else:
        envelope["error"] = str(error)[:1024]
    encoded = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise ProtectedDataProtocolError("Response exceeds the size limit.")
    return encoded


class ProtectedDataBackend:
    """Service-account owner of protected DB/key/backup artifacts."""

    def __init__(self, layout: ProtectedStorageLayout | None = None) -> None:
        self._layout = layout or get_protected_storage_layout()

    @property
    def layout(self) -> ProtectedStorageLayout:
        return self._layout

    def _load_key(self) -> bytes:
        return DatabaseKeyStore(
            bundle_path=self._layout.key_bundle_path,
            machine_scope=True,
        ).load()

    @staticmethod
    def _fsync(path: Path) -> None:
        with path.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())

    def health(self) -> dict[str, Any]:
        return {
            "service": self._layout.service_name,
            "protocol_version": PROTOCOL_VERSION,
            "database_present": self._layout.database_path.is_file(),
            "key_present": self._layout.key_bundle_path.is_file(),
            "metadata_present": self._layout.metadata_dir.is_dir(),
        }

    def validate_database(self) -> dict[str, Any]:
        key = self._load_key()
        validate_database_artifact(
            self._layout.database_path,
            encryption_required=True,
            key=key,
        )
        return {
            "valid": True,
            "database_sha256": _sha256(self._layout.database_path),
        }

    def create_backup(self, label: str) -> dict[str, Any]:
        if not _BACKUP_LABEL_RE.fullmatch(label):
            raise ProtectedDataBrokerError(
                "Backup label must contain only letters, numbers, '_' or '-' (1-48 chars)."
            )
        if not self._layout.metadata_dir.is_dir():
            raise ProtectedDataBrokerError(
                "Protected metadata is missing; refusing to create an incomplete recovery backup."
            )
        key = self._load_key()
        source = self._layout.database_path
        validate_database_artifact(source, encryption_required=True, key=key)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_id = f"{label}_{stamp}_{uuid.uuid4().hex[:8]}"
        destination_dir = self._layout.backup_dir / backup_id
        destination = destination_dir / "center.db"
        destination_dir.mkdir(parents=True, exist_ok=False)
        try:
            sqlcipher = load_sqlcipher_driver()
            src = sqlcipher.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
            dst = sqlcipher.connect(str(destination))
            try:
                apply_sqlcipher_key(src, key)
                src.execute("SELECT count(*) FROM sqlite_master").fetchone()
                apply_sqlcipher_key(dst, key)
                src.backup(dst)
                dst.commit()
            finally:
                dst.close()
                src.close()
            self._fsync(destination)
            validate_database_artifact(destination, encryption_required=True, key=key)

            metadata_target = destination_dir / "metadata"
            shutil.copytree(self._layout.metadata_dir, metadata_target)
            manifest = {
                "format_version": 1,
                "backup_id": backup_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "database": "center.db",
                "database_encrypted": True,
                "encryption": "sqlcipher-service-key-v1",
                "metadata": "metadata",
                "checksums": {"center.db": _sha256(destination)},
            }
            manifest_path = destination_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            self._fsync(manifest_path)
            return {
                "backup_id": backup_id,
                "database_sha256": manifest["checksums"]["center.db"],
            }
        except Exception:
            shutil.rmtree(destination_dir, ignore_errors=True)
            raise


class ProtectedDataBroker:
    """Dispatch OS-authenticated requests through service-owned authorization."""

    def __init__(
        self,
        backend: ProtectedDataBackend | None = None,
        domain_gateway: ProtectedDomainGateway | None = None,
    ) -> None:
        self._backend = backend or ProtectedDataBackend()
        self._domain = domain_gateway or ProtectedDomainGateway(self._backend.layout)

    @staticmethod
    def _token(payload: Mapping[str, Any]) -> str:
        return str(payload.get("session_token", ""))

    def dispatch(self, request: BrokerRequest, caller: CallerIdentity) -> dict[str, Any]:
        if not caller.sid:
            raise ProtectedDataBrokerError("Authenticated caller identity is required.")
        try:
            if request.operation is ProtectedDataOperation.HEALTH:
                return self._backend.health()
            if request.operation is ProtectedDataOperation.VALIDATE_DATABASE:
                return self._backend.validate_database()
            if request.operation is ProtectedDataOperation.AUTHENTICATE:
                return self._domain.authenticate(
                    str(request.payload.get("username", "")),
                    str(request.payload.get("password", "")),
                    caller.sid,
                )
            if request.operation is ProtectedDataOperation.LOGOUT:
                return self._domain.logout(self._token(request.payload), caller.sid)
            if request.operation is ProtectedDataOperation.STUDENT_LIST:
                return self._domain.list_students(self._token(request.payload), caller.sid)
            if request.operation is ProtectedDataOperation.STUDENT_CREATE:
                return self._domain.create_student(
                    self._token(request.payload),
                    caller.sid,
                    request.payload.get("student", {}),
                )
            if request.operation is ProtectedDataOperation.CREATE_BACKUP:
                # Backup is safe with respect to DB mutation but can consume disk;
                # it therefore requires a service-authenticated app user with the
                # canonical backup.create capability.
                self._domain._authorized_user(
                    self._token(request.payload), caller.sid, Capability.BACKUP_CREATE
                )
                return self._backend.create_backup(str(request.payload.get("label", "manual")))
        except ProtectedDomainError as exc:
            raise ProtectedDataBrokerError(str(exc)) from exc
        raise ProtectedDataProtocolError("Operation is not enabled by this broker version.")
