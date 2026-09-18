# -*- coding: utf-8 -*-
"""A3.3/A3.4 portable release contract tests."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_builder_pins_and_verifies_portable_git():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert "MinGit-2.54.0-64-bit.zip" in source
    assert "PORTABLE_GIT_SHA256" in source
    assert "hashlib.sha256" in source
    assert "bundle_portable_git()" in source
    assert 'target = PACKAGE_ROOT / "git"' in source
    assert 'target / "cmd" / "git.exe"' in source


def test_frozen_git_locator_uses_executable_directory():
    source = (
        ROOT / "src/centermanager/core/git_locator.py"
    ).read_text(encoding="utf-8")
    assert 'Path(sys.executable).resolve().parent' in source
    assert 'base_dir / "git" / "cmd" / "git.exe"' in source


def test_portable_smoke_entrypoint_is_available():
    source = (ROOT / "run.py").read_text(encoding="utf-8")
    assert "CENTERMANAGER_PORTABLE_SMOKE" in source
    assert "_portable_smoke_check" in source


def test_startup_does_not_require_git_configuration():
    source = (ROOT / "src/centermanager/app.py").read_text(encoding="utf-8")
    assert 'starting in local/offline mode' in source
    assert 'No Git configuration found' in source
    assert 'Git configuration is required to synchronize data' not in source
