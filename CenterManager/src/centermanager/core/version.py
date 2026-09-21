# -*- coding: utf-8 -*-
"""Canonical CenterManager application-version access.

Source execution reads the top-level ``VERSION`` file. Frozen production
execution reads ``RELEASE_MANIFEST.json`` beside the executable; PROD-02 builds
that manifest from the same VERSION file and validates it before upload.
"""

import json
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def _validate_version(version: str, source: Path) -> str:
    version = version.strip()
    if not SEMVER_RE.fullmatch(version):
        raise RuntimeError(f"Canonical version metadata is invalid in {source}: {version!r}")
    return version


def get_application_version() -> str:
    """Resolve immutable release identity for source or frozen execution."""
    if getattr(sys, "frozen", False):
        manifest_path = Path(sys.executable).resolve().parent / "RELEASE_MANIFEST.json"
        if not manifest_path.exists():
            raise RuntimeError(f"Release manifest is missing beside executable: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Release manifest is unreadable: {manifest_path}") from exc
        if manifest.get("application") != "CenterManager":
            raise RuntimeError(f"Release manifest application identity is invalid: {manifest_path}")
        return _validate_version(str(manifest.get("version", "")), manifest_path)

    version_path = Path(__file__).resolve().parents[3] / "VERSION"
    if not version_path.exists():
        raise RuntimeError(f"Canonical VERSION asset is missing: {version_path}")
    return _validate_version(version_path.read_text(encoding="utf-8"), version_path)


APPLICATION_VERSION = get_application_version()
