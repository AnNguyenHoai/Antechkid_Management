# -*- coding: utf-8 -*-
"""SEC-02 protected-storage policy and transition guard.

The current desktop application still opens SQLCipher directly in the GUI process.
That is acceptable only in transitional mode. Once Windows ACLs move the database
and key under a dedicated service identity, direct database access from the GUI
must fail closed rather than silently bypassing the service boundary.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


_PROTECTED_STORAGE_MODE_ENV = "ANTECHKIDS_PROTECTED_STORAGE_MODE"
_SERVICE_NAME = "AnTechKidsData"
_SERVICE_SID = rf"NT SERVICE\{_SERVICE_NAME}"
_PIPE_NAME = r"\\.\pipe\AnTechKidsData.v2"


class ProtectedStorageConfigurationError(RuntimeError):
    """Raised when protected-storage policy would be bypassed."""


class ProtectedStorageMode(str, Enum):
    TRANSITIONAL = "transitional"
    ENFORCED = "enforced"


@dataclass(frozen=True)
class ProtectedStorageLayout:
    root: Path
    database_dir: Path
    backup_dir: Path
    key_dir: Path
    metadata_dir: Path
    service_name: str = _SERVICE_NAME
    service_sid: str = _SERVICE_SID
    pipe_name: str = _PIPE_NAME

    @property
    def database_path(self) -> Path:
        return self.database_dir / "center.db"

    @property
    def key_bundle_path(self) -> Path:
        return self.key_dir / "database_key.dpapi"


def protected_storage_mode(env: Mapping[str, str] | None = None) -> ProtectedStorageMode:
    values = os.environ if env is None else env
    raw = str(values.get(_PROTECTED_STORAGE_MODE_ENV, "transitional")).strip().lower()
    try:
        return ProtectedStorageMode(raw)
    except ValueError as exc:
        raise ProtectedStorageConfigurationError(
            f"Unsupported {_PROTECTED_STORAGE_MODE_ENV} value: {raw!r}"
        ) from exc


def get_protected_storage_layout(
    env: Mapping[str, str] | None = None,
    *,
    program_data: Path | None = None,
) -> ProtectedStorageLayout:
    """Return the service-owned production storage layout without creating it."""
    values = os.environ if env is None else env
    base = program_data
    if base is None:
        configured = str(values.get("PROGRAMDATA", "")).strip()
        if not configured:
            if os.name == "nt":
                raise ProtectedStorageConfigurationError(
                    "PROGRAMDATA is unavailable; cannot resolve protected storage."
                )
            configured = "/var/lib"
        base = Path(configured)
    root = Path(base) / "AnTechKids" / "CenterManager" / "Protected"
    return ProtectedStorageLayout(
        root=root,
        database_dir=root / "Database",
        backup_dir=root / "Backup",
        key_dir=root / "Key",
        metadata_dir=root / "metadata",
    )


def assert_direct_database_access_allowed(
    env: Mapping[str, str] | None = None,
) -> None:
    """Fail closed if GUI/local code tries to open DB in enforced service mode.

    SEC-02 is intentionally staged. Until a broker-backed SQLAlchemy/repository
    adapter exists, enabling ``enforced`` must stop direct database access. This
    prevents a future deployment from applying service-only ACLs while the GUI
    accidentally continues loading the raw workspace key under the employee token.
    """
    mode = protected_storage_mode(env)
    if mode is ProtectedStorageMode.ENFORCED:
        raise ProtectedStorageConfigurationError(
            "Protected storage is enforced: direct database access from the desktop "
            "process is forbidden. Configure the AnTechKidsData service-backed "
            "database broker before enabling enforced mode."
        )
