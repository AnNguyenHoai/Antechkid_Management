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


def test_startup_prompts_when_git_is_not_ready_for_this_machine():
    source = (
        ROOT
        / "src/centermanager/platform/bootstrap/bootstrap_manager.py"
    ).read_text(encoding="utf-8")
    assert "GitConfigDialog" in source
    assert "credential_status = git_config_service.credential_status()" in source
    assert '"not_provisioned_on_this_machine"' in source
    assert '"legacy_not_provisioned_on_this_machine"' in source
    assert "requesting local provisioning" in source
    assert "dialog.exec() != dialog.DialogCode.Accepted" in source
    assert "Git configuration was not available after local provisioning" in source
    assert "starting in local/offline mode" not in source
