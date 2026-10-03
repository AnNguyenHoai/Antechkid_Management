# -*- coding: utf-8 -*-
"""Regression tests for frozen release manifest resolution."""

import json
from pathlib import Path

import pytest

from centermanager.core.version import _resolve_frozen_manifest_path


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps({"application": "CenterManager", "version": "1.0.0"}),
        encoding="utf-8",
    )


def test_resolve_manifest_beside_main_executable(tmp_path: Path):
    executable = tmp_path / "CenterManager.exe"
    executable.touch()
    manifest = tmp_path / "RELEASE_MANIFEST.json"
    _write_manifest(manifest)

    assert _resolve_frozen_manifest_path(executable) == manifest.resolve()


def test_resolve_manifest_from_admintools_parent(tmp_path: Path):
    admin_dir = tmp_path / "AdminTools"
    admin_dir.mkdir()
    executable = admin_dir / "GitProvisioningAdmin.exe"
    executable.touch()
    manifest = tmp_path / "RELEASE_MANIFEST.json"
    _write_manifest(manifest)

    assert _resolve_frozen_manifest_path(executable) == manifest.resolve()


def test_manifest_resolver_does_not_walk_arbitrary_ancestors(tmp_path: Path):
    nested = tmp_path / "OtherTools"
    nested.mkdir()
    executable = nested / "UnexpectedTool.exe"
    executable.touch()
    _write_manifest(tmp_path / "RELEASE_MANIFEST.json")

    with pytest.raises(RuntimeError, match="Release manifest is missing"):
        _resolve_frozen_manifest_path(executable)
