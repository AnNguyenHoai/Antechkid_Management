# -*- coding: utf-8 -*-
"""Canonical CenterManager application-version access.

Source execution reads the top-level ``VERSION`` file. Frozen production
execution reads ``RELEASE_MANIFEST.json`` from the release root; PROD-02 builds
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


def _resolve_frozen_manifest_path(executable: Path) -> Path:
    """Resolve the manifest for a supported frozen executable layout.

    CenterManager.exe lives at the release root. Administrator utilities live
    exactly one level below it in ``AdminTools``. Deliberately do not walk
    arbitrary ancestors: release identity must come from the expected package
    layout rather than from an unrelated manifest elsewhere on disk.
    """
    executable = Path(executable).resolve()
    executable_dir = executable.parent

    direct = executable_dir / "RELEASE_MANIFEST.json"
    if direct.is_file():
        return direct

    candidates = [direct]
    if executable_dir.name.casefold() == "admintools":
        parent_manifest = executable_dir.parent / "RELEASE_MANIFEST.json"
        candidates.append(parent_manifest)
        if parent_manifest.is_file():
            return parent_manifest

    expected = " or ".join(str(path) for path in candidates)
    raise RuntimeError(
        f"Release manifest is missing for executable {executable}; expected {expected}"
    )


def get_release_root() -> Path:
    """Return the canonical CenterManager release/source root."""
    if getattr(sys, "frozen", False):
        return _resolve_frozen_manifest_path(Path(sys.executable)).parent
    return Path(__file__).resolve().parents[3]


def get_application_version() -> str:
    """Resolve immutable release identity for source or frozen execution."""
    if getattr(sys, "frozen", False):
        manifest_path = _resolve_frozen_manifest_path(Path(sys.executable))
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Release manifest is unreadable: {manifest_path}") from exc
        if manifest.get("application") != "CenterManager":
            raise RuntimeError(f"Release manifest application identity is invalid: {manifest_path}")
        return _validate_version(str(manifest.get("version", "")), manifest_path)

    version_path = get_release_root() / "VERSION"
    if not version_path.exists():
        raise RuntimeError(f"Canonical VERSION asset is missing: {version_path}")
    return _validate_version(version_path.read_text(encoding="utf-8"), version_path)


APPLICATION_VERSION = get_application_version()
