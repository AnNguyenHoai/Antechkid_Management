# -*- coding: utf-8 -*-
"""SQLCipher database encryption and key-management boundary.

Windows production databases use a 256-bit workspace key protected locally by
Windows DPAPI. The raw key is never persisted on disk. Each workstation stores
its own DPAPI-wrapped copy of the shared workspace key so encrypted Git database
artifacts remain readable across authorized CenterManager machines without
leaving a plaintext key beside the database.
"""
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path
from typing import Any

from centermanager.core.paths import get_paths
from centermanager.core.secret_store import (
    SecretStoreUnavailable,
    protect_secret,
    unprotect_secret,
)


_KEY_BYTES = 32
_KEY_BUNDLE_VERSION = "DBKEY:v1:"
_FORCE_ENCRYPTION_ENV = "ANTECHKIDS_FORCE_DATABASE_ENCRYPTION"


class DatabaseEncryptionError(RuntimeError):
    """Base error for the encrypted database boundary."""


class DatabaseEncryptionDriverUnavailable(DatabaseEncryptionError):
    """Raised when SQLCipher is required but its Python driver is unavailable."""


class DatabaseKeyUnavailable(DatabaseEncryptionError):
    """Raised when the production database key cannot be loaded safely."""


def database_encryption_required() -> bool:
    """Return whether this runtime must use SQLCipher.

    CenterManager production is Windows-targeted. CI and developer hosts on
    other platforms keep the historical SQLite path unless tests explicitly
    force the encrypted boundary.
    """
    forced = os.environ.get(_FORCE_ENCRYPTION_ENV, "").strip().lower()
    return os.name == "nt" or forced in {"1", "true", "yes", "on"}


def load_sqlcipher_driver() -> Any:
    """Load SQLCipher DB-API without silently falling back to stdlib SQLite."""
    try:
        from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore
    except Exception as exc:  # pragma: no cover - platform/package dependent
        raise DatabaseEncryptionDriverUnavailable(
            "SQLCipher is required for the production database but the "
            "sqlcipher3 driver is unavailable."
        ) from exc
    return sqlcipher


class DatabaseKeyStore:
    """Persist a workspace DB key as a local DPAPI-protected bundle."""

    def __init__(self, bundle_path: Path | None = None) -> None:
        self._bundle_path = Path(bundle_path) if bundle_path else (
            get_paths().config_dir / "database_key.dpapi"
        )

    @property
    def bundle_path(self) -> Path:
        return self._bundle_path

    @staticmethod
    def _encode_key(key: bytes) -> str:
        if len(key) != _KEY_BYTES:
            raise DatabaseKeyUnavailable("Database key must be exactly 256 bits.")
        return base64.b64encode(key).decode("ascii")

    @staticmethod
    def _decode_key(value: str) -> bytes:
        try:
            key = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise DatabaseKeyUnavailable("Invalid protected database key payload.") from exc
        if len(key) != _KEY_BYTES:
            raise DatabaseKeyUnavailable("Invalid protected database key length.")
        return key

    def load(self) -> bytes:
        """Load an existing key; never create a replacement implicitly."""
        if not self._bundle_path.is_file():
            raise DatabaseKeyUnavailable(
                "Protected database key is missing; recovery is required."
            )
        try:
            bundle = self._bundle_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise DatabaseKeyUnavailable("Protected database key is unreadable.") from exc
        if not bundle.startswith(_KEY_BUNDLE_VERSION):
            raise DatabaseKeyUnavailable("Unsupported database key bundle format.")
        protected = bundle[len(_KEY_BUNDLE_VERSION):]
        try:
            plaintext = unprotect_secret(protected)
        except (SecretStoreUnavailable, ValueError, OSError) as exc:
            raise DatabaseKeyUnavailable(
                "Database key cannot be unprotected on this Windows user/machine."
            ) from exc
        return self._decode_key(plaintext)

    def provision(self, key: bytes, *, overwrite: bool = False) -> bytes:
        """Persist an explicitly supplied workspace key under local DPAPI.

        Provisioning is intentionally separate from normal application startup.
        It is used by trusted deployment/migration flows on each authorized
        workstation. Existing key material is never replaced unless the caller
        explicitly requests an overwrite.
        """
        if len(key) != _KEY_BYTES:
            raise DatabaseKeyUnavailable("Database key must be exactly 256 bits.")
        if self._bundle_path.exists() and not overwrite:
            existing = self.load()
            if existing != key:
                raise DatabaseKeyUnavailable(
                    "A different protected database key is already provisioned."
                )
            return existing
        try:
            protected = protect_secret(self._encode_key(key))
        except SecretStoreUnavailable as exc:
            raise DatabaseKeyUnavailable(
                "Windows DPAPI is required to provision a production database key."
            ) from exc
        self._bundle_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._bundle_path.with_name(self._bundle_path.name + ".tmp")
        try:
            tmp.write_text(_KEY_BUNDLE_VERSION + protected, encoding="utf-8")
            os.replace(tmp, self._bundle_path)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise DatabaseKeyUnavailable("Failed to persist protected database key.") from exc
        return key

    def create(self) -> bytes:
        """Generate and provision a new workspace key exactly once."""
        if self._bundle_path.exists():
            return self.load()
        return self.provision(secrets.token_bytes(_KEY_BYTES))

    def load_or_create(self, *, allow_create: bool) -> bytes:
        """Load existing key, creating only during explicit first-run setup."""
        if self._bundle_path.exists():
            return self.load()
        if not allow_create:
            raise DatabaseKeyUnavailable(
                "Protected database key is missing; refusing to create a new key "
                "for an existing/production database."
            )
        return self.create()


def apply_sqlcipher_key(connection: Any, key: bytes) -> None:
    """Apply a raw 256-bit key before any schema access and verify SQLCipher."""
    if len(key) != _KEY_BYTES:
        raise DatabaseKeyUnavailable("Database key must be exactly 256 bits.")
    cursor = connection.cursor()
    try:
        cursor.execute(f'PRAGMA key = "x\'{key.hex()}\'";')
        row = cursor.execute("PRAGMA cipher_version;").fetchone()
        if not row or not str(row[0]).strip():
            raise DatabaseEncryptionDriverUnavailable(
                "Loaded database driver does not expose SQLCipher support."
            )
    finally:
        cursor.close()


def is_plaintext_sqlite_file(path: Path) -> bool:
    """Detect the standard SQLite plaintext header without parsing DB content."""
    try:
        with Path(path).open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False
