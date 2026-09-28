# -*- coding: utf-8 -*-
"""Signed identity contract for the Git-authoritative database artifact.

The SQLCipher workspace key proves that a database can be decrypted, but that is
not sufficient to prove that the file is the expected collaboration database.
This module binds each published repository DB to a stable ``database_id``, a
monotonic generation and the exact artifact bytes using HMAC-SHA256.

A workstation pins the first valid signed identity it sees (TOFU). Subsequent
validations reject a different database id and reject a generation lower than
its locally pinned floor. This detects repository substitution/rollback while
the local pin remains intact; it is not claimed to survive rollback of the local
machine state itself.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from centermanager.core.paths import get_paths


FORMAT_VERSION = 1
_MANIFEST_SUFFIX = ".identity.json"
_STATE_FILE = "authoritative_database_identity.json"
_MANIFEST_DOMAIN = b"antechkids-db-artifact-identity-v1\0"
_STATE_DOMAIN = b"antechkids-db-local-identity-v1\0"


class DatabaseArtifactIdentityError(RuntimeError):
    """Raised when the authoritative DB identity contract is violated."""


@dataclass(frozen=True)
class DatabaseArtifactIdentity:
    database_id: str
    generation: int
    sha256: str


def identity_manifest_path(database_path: Path) -> Path:
    database_path = Path(database_path)
    return database_path.with_name(database_path.name + _MANIFEST_SUFFIX)


def local_identity_state_path() -> Path:
    return get_paths().config_dir / _STATE_FILE


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sign(payload: dict, key: bytes, *, domain: bytes) -> str:
    return hmac.new(key, domain + _canonical(payload), hashlib.sha256).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, document: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        tmp.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with tmp.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _document(payload: dict, key: bytes, *, domain: bytes) -> dict:
    return {
        "payload": payload,
        "hmac_sha256": _sign(payload, key, domain=domain),
    }


def _load_signed_document(path: Path, key: bytes, *, domain: bytes) -> dict:
    path = Path(path)
    if not path.is_file():
        raise DatabaseArtifactIdentityError(f"Signed database identity is missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        payload = document["payload"]
        supplied = str(document["hmac_sha256"])
    except Exception as exc:
        raise DatabaseArtifactIdentityError(
            f"Signed database identity is malformed: {path}"
        ) from exc
    expected = _sign(payload, key, domain=domain)
    if not hmac.compare_digest(supplied, expected):
        raise DatabaseArtifactIdentityError(
            f"Signed database identity authentication failed: {path}"
        )
    return payload


def _parse_identity(payload: dict) -> DatabaseArtifactIdentity:
    try:
        if int(payload["format_version"]) != FORMAT_VERSION:
            raise ValueError("unsupported format")
        database_id = str(uuid.UUID(str(payload["database_id"])))
        generation = int(payload["generation"])
        sha256 = str(payload["sha256"]).lower()
        if generation < 1:
            raise ValueError("generation must be positive")
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("invalid sha256")
    except Exception as exc:
        raise DatabaseArtifactIdentityError("Invalid database identity payload") from exc
    return DatabaseArtifactIdentity(database_id, generation, sha256)


def build_identity_document(
    database_path: Path,
    key: bytes,
    *,
    database_id: str,
    generation: int,
) -> dict:
    """Build a signed manifest for exact bytes at ``database_path``."""
    identity = DatabaseArtifactIdentity(
        database_id=str(uuid.UUID(str(database_id))),
        generation=int(generation),
        sha256=_sha256(database_path),
    )
    if identity.generation < 1:
        raise DatabaseArtifactIdentityError("Database generation must be positive")
    payload = {
        "format_version": FORMAT_VERSION,
        "database_id": identity.database_id,
        "generation": identity.generation,
        "sha256": identity.sha256,
    }
    return _document(payload, key, domain=_MANIFEST_DOMAIN)


def next_identity_document(database_path: Path, key: bytes, current_database_path: Path) -> dict:
    """Create the next publication identity, preserving the stable database id."""
    current_manifest = identity_manifest_path(current_database_path)
    if current_manifest.is_file():
        current = _parse_identity(
            _load_signed_document(current_manifest, key, domain=_MANIFEST_DOMAIN)
        )
        database_id = current.database_id
        generation = current.generation + 1
    else:
        database_id = str(uuid.uuid4())
        generation = 1
    return build_identity_document(
        database_path,
        key,
        database_id=database_id,
        generation=generation,
    )


def write_identity_document(path: Path, document: dict) -> None:
    _atomic_write_json(path, document)


def validate_and_pin_identity(database_path: Path, key: bytes) -> DatabaseArtifactIdentity:
    """Verify signature/hash and enforce the workstation's pinned identity floor."""
    database_path = Path(database_path)
    manifest = identity_manifest_path(database_path)
    identity = _parse_identity(
        _load_signed_document(manifest, key, domain=_MANIFEST_DOMAIN)
    )
    actual_hash = _sha256(database_path)
    if not hmac.compare_digest(identity.sha256, actual_hash):
        raise DatabaseArtifactIdentityError(
            "Authoritative database bytes do not match the signed identity manifest"
        )

    state_path = local_identity_state_path()
    if state_path.is_file():
        state_payload = _load_signed_document(state_path, key, domain=_STATE_DOMAIN)
        try:
            pinned_id = str(uuid.UUID(str(state_payload["database_id"])))
            floor = int(state_payload["highest_generation"])
        except Exception as exc:
            raise DatabaseArtifactIdentityError("Invalid local database identity pin") from exc
        if pinned_id != identity.database_id:
            raise DatabaseArtifactIdentityError(
                "Authoritative database identity does not match the locally pinned workspace database"
            )
        if identity.generation < floor:
            raise DatabaseArtifactIdentityError(
                "Authoritative database generation is older than the locally trusted generation"
            )
        if identity.generation == floor:
            return identity

    state_payload = {
        "format_version": FORMAT_VERSION,
        "database_id": identity.database_id,
        "highest_generation": identity.generation,
    }
    _atomic_write_json(
        state_path,
        _document(state_payload, key, domain=_STATE_DOMAIN),
    )
    return identity
