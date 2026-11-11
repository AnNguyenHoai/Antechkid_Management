"""Independent, machine-key authenticated cache proof for safe offline READ.

Not a Recovery journal, user acknowledgement, WRITE grant, or publication
receipt. It exists solely to prove that a cached runtime was previously
authenticated against Git MAIN before network access was lost.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from pathlib import Path

from centermanager.core.paths import get_paths


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _secret() -> bytes:
    from centermanager.database.encryption import (
        DatabaseKeyStore, database_encryption_required,
    )
    if not database_encryption_required():
        raise ValueError("Unencrypted workspace has no protected offline cache key")
    key = DatabaseKeyStore().load()
    if not isinstance(key, (bytes, str)):
        raise ValueError("Invalid encrypted workspace key")
    return key.encode("utf-8") if isinstance(key, str) else key


def _path(paths) -> Path:
    runtime = Path(paths.runtime_root).resolve()
    return runtime.with_name(runtime.name + ".accepted-main") / "read-cache.json"


def _signature(data: dict, key: bytes) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(
        key, b"CenterManager:independent-cached-main:v1\\0" + payload,
        hashlib.sha256,
    ).hexdigest()


def record_authenticated_main(provider, paths=None) -> None:
    """Best-effort durable cache after online Git/SQLCipher/schema validation.

    Caller decides when online MAIN is verified. Failure must only reduce
    offline availability, never interrupt an otherwise healthy online session.
    """
    paths = paths or get_paths()
    local = provider.get_local_main_commit()
    observed = provider.observe_remote_main_commit()
    if (not isinstance(local, str) or not re.fullmatch(r"[0-9a-f]{40}", local)
            or local != observed):
        raise ValueError("Exact authoritative Git MAIN OID unavailable")
    root = Path(paths.runtime_root)
    db = Path(paths.database_dir) / "center.db"
    repo_db = root / "repository" / "database" / "center.db"
    if (not db.is_file() or not repo_db.is_file()
            or db.is_symlink() or repo_db.is_symlink()):
        raise ValueError("Missing/symlinked authenticated MAIN artifacts")
    key = _secret()
    payload = {
        "version": 1,
        "accepted_main_oid": local,
        "runtime_db_sha256": _digest(db),
        "repository_db_sha256": _digest(repo_db),
    }
    location = _path(paths)
    location.parent.mkdir(parents=True, exist_ok=True)
    temporary = location.with_name("." + location.name + "-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(
                {"payload": payload, "mac": _signature(payload, key)},
                output, sort_keys=True,
            )
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, location)
    finally:
        temporary.unlink(missing_ok=True)


def verify_authenticated_cache(paths=None) -> bool:
    """Never mutate the runtime or trust a historical Recovery receipt."""
    paths = paths or get_paths()
    location = _path(paths)
    if not location.is_file() or location.is_symlink():
        return False
    data = json.loads(location.read_text(encoding="utf-8"))
    payload = data.get("payload")
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return False
    oid = payload.get("accepted_main_oid")
    if not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{40}", oid):
        return False
    if not hmac.compare_digest(str(data.get("mac", "")), _signature(payload, _secret())):
        return False
    root = Path(paths.runtime_root)
    db = Path(paths.database_dir) / "center.db"
    repo_db = root / "repository" / "database" / "center.db"
    if (not db.is_file() or not repo_db.is_file()
            or db.is_symlink() or repo_db.is_symlink()):
        return False
    return (
        hmac.compare_digest(_digest(db), str(payload.get("runtime_db_sha256", "")))
        and hmac.compare_digest(
            _digest(repo_db), str(payload.get("repository_db_sha256", ""))
        )
    )
