"""Signed, immutable evidence of PR-633 startup rollback DB/WAL generation.

The startup hook is strictly best-effort: failure never prevents Git MAIN
startup. An unbound rollback must remain UNVERIFIED. No automatic plaintext.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

_FILES = ("center.db", "center.db-wal", "center.db-shm", "center.db-journal", "database_key.dpapi")
_DOMAIN = b"AnTechKids/REC635/startup-rollback-proof/v1\0"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sign(body: dict, key: bytes) -> str:
    return hmac.new(
        key, _DOMAIN + json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _proof_path(notices, notice: dict) -> Path:
    return notices.root / (notice["id"] + ".rollback-proof.json")


def _check_directory(notices, directory: Path) -> Path:
    root = (Path(notices.journal.root) / "startup-rollbacks").resolve()
    directory = Path(directory)
    if (directory.is_symlink() or not directory.is_dir()
            or directory.parent.resolve() != root or not root.is_dir()):
        raise ValueError("Untrusted startup rollback directory")
    return directory.resolve()


def _key(provided: bytes | None) -> bytes:
    if provided is not None:
        if len(provided) != 32:
            raise ValueError("Expected 256-bit recovery proof key")
        return provided
    from centermanager.database.encryption import DatabaseKeyStore
    return DatabaseKeyStore().load()


def bind_startup_rollback(notices, notice_path: Path, rollback_dir: Path, *,
                          encryption_key: bytes | None = None) -> Path:
    """Bind the old DB and detached WAL to *this* notice without blocking startup.

    Caller should invoke only after runtime replacement succeeds and only on
    the special review-only startup path; exceptions are handled by caller.
    """
    notice = notices.validate_notice(notice_path)
    proof_path = _proof_path(notices, notice)
    key = _key(encryption_key)
    if proof_path.exists():
        # Idempotent: never overwrite an earlier incident's signed evidence.
        verify_startup_rollback(notices, notice, encryption_key=key)
        return proof_path
    directory = _check_directory(notices, rollback_dir)
    db = directory / "center.db"
    if not db.is_file() or db.is_symlink():
        raise ValueError("No old DB preserved for this recovery incident")
    from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required
    if database_encryption_required():
        bundle = directory / "database_key.dpapi"
        if not bundle.exists():
            source = DatabaseKeyStore().bundle_path
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing original SQLCipher key bundle")
            with source.open("rb") as stream, bundle.open("xb") as target:
                shutil.copyfileobj(stream, target)
                target.flush()
                os.fsync(target.fileno())
    files = {}
    for name in _FILES:
        path = directory / name
        if path.is_symlink():
            raise ValueError("Unsafe rollback sidecar")
        if path.exists():
            if not path.is_file():
                raise ValueError("Unexpected rollback artifact")
            files[name] = _hash(path)
    body = {
        "format": 1,
        "notice_id": notice["id"],
        "observed_main_oid": notice["observed_main_oid"],
        "journal_sha256": notice["journal_sha256"],
        "directory": str(directory),
        "files": files,
    }
    signed = {**body, "hmac_sha256": _sign(body, key)}
    temp = proof_path.with_name("." + proof_path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as output:
            os.chmod(temp, 0o600)
            json.dump(signed, output, sort_keys=True, indent=2)
            output.flush()
            os.fsync(output.fileno())
        # Never replace evidence for a prior independently recorded incident.
        with proof_path.open("xb") as dest, temp.open("rb") as src:
            shutil.copyfileobj(src, dest)
            dest.flush()
            os.fsync(dest.fileno())
    finally:
        temp.unlink(missing_ok=True)
    verify_startup_rollback(notices, notice, encryption_key=key)
    return proof_path


def verify_startup_rollback(notices, notice: dict, *,
                            encryption_key: bytes | None = None) -> Path:
    """Authenticate the notice, signed proof, file hashes and exact parent."""
    current = notices.validate_notice(notices.root / (notice["id"] + ".json"))
    if current != notice:
        raise ValueError("Recovery notice changed")
    proof_path = _proof_path(notices, notice)
    if proof_path.is_symlink() or not proof_path.is_file():
        raise ValueError("Recovery rollback has no signed proof")
    signed = json.loads(proof_path.read_text(encoding="utf-8"))
    signature = signed.pop("hmac_sha256", None)
    if not isinstance(signature, str) or not hmac.compare_digest(
        signature, _sign(signed, _key(encryption_key))
    ):
        raise ValueError("Recovery rollback proof authentication failed")
    if (signed.get("format") != 1 or signed.get("notice_id") != notice["id"]
            or signed.get("observed_main_oid") != notice["observed_main_oid"]
            or signed.get("journal_sha256") != notice["journal_sha256"]):
        raise ValueError("Recovery rollback proof bound to another incident")
    directory = _check_directory(notices, Path(signed["directory"]))
    files = signed.get("files")
    if not isinstance(files, dict) or not files.get("center.db"):
        raise ValueError("Recovery rollback proof lacks captured DB")
    for name in _FILES:
        path = directory / name
        if path.is_symlink():
            raise ValueError("Recovery rollback has unexpected symlink")
        if (name in files) != path.is_file():
            raise ValueError("Recovery rollback file inventory changed")
        if name in files and not hmac.compare_digest(_hash(path), files[name]):
            raise ValueError("Recovery rollback file hash mismatch")
    return directory


@contextmanager
def reconstructed_readonly_snapshot(notices, notice: dict, *,
                                    encryption_key: bytes | None = None):
    """Use only an isolated temporary DB to replay old WAL and checkpoint it.

    The old rollback bytes remain unchanged. The canonicalized temporary DB is
    never exported and is removed even on error. SQLCipher remains encrypted.
    """
    key = _key(encryption_key)
    directory = verify_startup_rollback(notices, notice, encryption_key=key)
    from centermanager.database.encryption import (
        DatabaseKeyStore, database_encryption_required,
        load_sqlcipher_driver, apply_sqlcipher_key,
    )
    from centermanager.database.artifact_security import validate_database_artifact
    encrypted = database_encryption_required()
    old_key = DatabaseKeyStore(directory / "database_key.dpapi").load() if encrypted else None
    with tempfile.TemporaryDirectory(prefix="rec635-snapshot-") as temp_dir:
        target = Path(temp_dir) / "center.db"
        for name in _FILES:
            if name == "database_key.dpapi":
                continue
            if (directory / name).is_file():
                shutil.copy2(directory / name, Path(temp_dir) / name)
        driver = load_sqlcipher_driver() if encrypted else __import__("sqlite3")
        connection = driver.connect(str(target))
        try:
            if encrypted:
                apply_sqlcipher_key(connection, old_key)
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("PRAGMA journal_mode=DELETE")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("Reconstructed SQLCipher recovery DB integrity failed")
        finally:
            connection.close()
        validate_database_artifact(target, encryption_required=encrypted, key=old_key)
        yield target, old_key
    verify_startup_rollback(notices, notice, encryption_key=key)
