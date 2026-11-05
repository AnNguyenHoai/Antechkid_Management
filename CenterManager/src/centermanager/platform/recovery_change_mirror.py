"""Protected RV-02 mirror of *committed* business operation metadata.

A mirrored event is a best-effort, encrypted human-review index. The only
authoritative evidence of whether all local operations were committed is the
verified SQLCipher recovery capture and its transaction-bound outbox. Do not
replay these records into a newer Git MAIN.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from centermanager.models.recovery_change_event import RecoveryChangeEvent

_AAD = b"AnTechKids/RV-02/committed-business-event/v1"
_SESSION_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")


def _payload(event: RecoveryChangeEvent) -> bytes:
    return json.dumps({
        "format": 1,
        "event_id": event.event_id,
        "operation_id": event.operation_id,
        "write_session_id": event.write_session_id,
        "base_main_oid": event.base_main_oid,
        "occurred_at_utc": event.occurred_at_utc.isoformat(),
        "actor_id": event.actor_id,
        "module": event.module,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "summary_code": event.summary_code,
        "summary_args_json": event.summary_args_json,
    }, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def _fsync_dir(directory: Path) -> None:
    if os.name != "nt":
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def mirror_committed_event(
    event: RecoveryChangeEvent,
    *,
    recovery_root: Path,
    encryption_key: bytes,
) -> Path:
    """Store one event at a deterministic, immutable, encrypted path.

    Call **only after the SQLCipher transaction committed**. Caller must
    separately track completeness; successful mirrored files never certify that
    all committed events were exported. No plaintext PII or SQL parameters.
    """
    if not isinstance(encryption_key, bytes) or len(encryption_key) not in (16, 24, 32):
        raise ValueError("Valid AES-GCM workspace key is required")
    session_id = event.write_session_id
    if not _SESSION_PATTERN.fullmatch(session_id or ""):
        raise ValueError("Invalid session identifier for recovery mirror")
    try:
        event_id = str(uuid.UUID(event.event_id))
    except ValueError as exc:
        raise ValueError("Invalid recovery event ID") from exc
    directory = Path(recovery_root) / "rv02-committed-events" / session_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / (event_id + ".enc")

    # Existing event must be authenticated and bytewise semantically identical.
    plaintext = _payload(event)
    if target.exists():
        if decrypt_mirrored_event(target, encryption_key=encryption_key) != json.loads(plaintext):
            raise ValueError("Existing immutable recovery event differs from committed source")
        return target

    nonce = os.urandom(12)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext, _AAD)
    temporary = directory / ("." + event_id + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(nonce + ciphertext)
            stream.flush()
            os.fsync(stream.fileno())
        # Do not overwrite if another publisher already mirrored this event.
        try:
            os.link(temporary, target)
        except FileExistsError:
            if decrypt_mirrored_event(target, encryption_key=encryption_key) != json.loads(plaintext):
                raise ValueError("Concurrent mirror contains different event data")
        except OSError:
            # Windows / filesystem may not support hard links; fallback to an
            # exclusive destination and fsync, never replace existing event.
            try:
                with target.open("xb") as stream:
                    os.chmod(target, 0o600)
                    stream.write(nonce + ciphertext)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                if decrypt_mirrored_event(target, encryption_key=encryption_key) != json.loads(plaintext):
                    raise ValueError("Concurrent mirror contains different event data")
        _fsync_dir(directory)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def decrypt_mirrored_event(path: Path, *, encryption_key: bytes) -> dict:
    """Authenticated read; only privileged offline recovery/report code may call."""
    encrypted = Path(path).read_bytes()
    if len(encrypted) < 29:
        raise ValueError("Truncated recovery event")
    return json.loads(AESGCM(encryption_key).decrypt(encrypted[:12], encrypted[12:], _AAD))


def assess_mirror_coverage(
    events: list[RecoveryChangeEvent],
    *,
    recovery_root: Path,
    encryption_key: bytes,
    committed_source_attested: bool,
) -> dict:
    """Compare encrypted mirror with a *complete, attested* committed outbox view.

    Returns UNKNOWN unless caller proves that the supplied event list covers a
    trusted SQLCipher session snapshot. RV-03 must verify backup integrity and
    its session ID before setting committed_source_attested=True. A missing or
    corrupt segment cannot be reported as a complete Recovery Change Log.
    """
    if not committed_source_attested:
        return {"status": "UNKNOWN", "expected": len(events), "verified": 0}
    verified = 0
    for event in events:
        try:
            if not _SESSION_PATTERN.fullmatch(event.write_session_id or ""):
                return {"status": "INCOMPLETE", "expected": len(events), "verified": verified}
            expected = (
                Path(recovery_root) / "rv02-committed-events"
                / event.write_session_id / (str(uuid.UUID(event.event_id)) + ".enc")
            )
            payload = decrypt_mirrored_event(expected, encryption_key=encryption_key)
            if payload != json.loads(_payload(event)):
                return {"status": "INCOMPLETE", "expected": len(events), "verified": verified}
            verified += 1
        except (OSError, ValueError, TypeError, KeyError):
            return {"status": "INCOMPLETE", "expected": len(events), "verified": verified}
        except Exception:
            return {"status": "INCOMPLETE", "expected": len(events), "verified": verified}
    return {"status": "COMPLETE", "expected": len(events), "verified": verified}
