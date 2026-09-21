# -*- coding: utf-8 -*-
"""Canonical CenterManager application-version access.

The release version value lives in the top-level ``VERSION`` file. Production
builds bundle that file into the PyInstaller application so runtime identity,
Windows metadata, release manifests, and package names all resolve from the
same source of truth.
"""

import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def _version_file() -> Path:
    """Return the immutable VERSION asset for source or frozen execution."""
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return bundle_root / "VERSION"
    return Path(__file__).resolve().parents[3] / "VERSION"


def get_application_version() -> str:
    """Read and validate the canonical application release version."""
    path = _version_file()
    if not path.exists():
        raise RuntimeError(f"Canonical VERSION asset is missing: {path}")
    version = path.read_text(encoding="utf-8").strip()
    if not SEMVER_RE.fullmatch(version):
        raise RuntimeError(f"Canonical VERSION asset is invalid: {version!r}")
    return version


APPLICATION_VERSION = get_application_version()
