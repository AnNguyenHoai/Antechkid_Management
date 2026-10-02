# -*- coding: utf-8 -*-
"""Regression coverage for cross-machine Git ref contamination."""

from pathlib import Path

import centermanager.platform.sync.startup_sync as startup_sync_module
from centermanager.platform.sync.startup_sync import StartupSynchronization
from centermanager.platform.synchronization.git_repository_hygiene import (
    remove_windows_shell_metadata_from_git_refs,
)


class _FakePaths:
    def __init__(self, root: Path):
        self.runtime_root = root / "runtime"
        self.database_dir = self.runtime_root / "Database"
        self.attachment_dir = self.runtime_root / "Attachments"
        self.metadata_dir = self.runtime_root / "metadata"
        self.database_dir.mkdir(parents=True)
        self.attachment_dir.mkdir(parents=True)
        self.metadata_dir.mkdir(parents=True)


class _FetchAssertingProvider:
    def __init__(self, contaminant: Path):
        self.contaminant = contaminant
        self.calls = []

    def connect(self):
        self.calls.append("connect")
        return True

    def fetch(self):
        self.calls.append("fetch")
        assert not self.contaminant.exists()
        return True

    def reset_to_remote(self):
        self.calls.append("reset")
        return True


def test_git_ref_hygiene_removes_only_desktop_ini_under_refs(tmp_path):
    repo = tmp_path / "repository"
    refs = repo / ".git" / "refs"
    heads = refs / "heads"
    heads.mkdir(parents=True)

    root_contaminant = refs / "desktop.ini"
    nested_contaminant = heads / "desktop.ini"
    valid_ref = heads / "main"
    outside_metadata = repo / "desktop.ini"

    root_contaminant.write_text("shell metadata", encoding="utf-8")
    nested_contaminant.write_text("shell metadata", encoding="utf-8")
    valid_ref.write_text("0123456789abcdef", encoding="utf-8")
    outside_metadata.write_text("keep me", encoding="utf-8")

    assert remove_windows_shell_metadata_from_git_refs(repo) is True
    assert not root_contaminant.exists()
    assert not nested_contaminant.exists()
    assert valid_ref.read_text(encoding="utf-8") == "0123456789abcdef"
    assert outside_metadata.read_text(encoding="utf-8") == "keep me"


def test_startup_removes_git_ref_contamination_before_fetch(tmp_path, monkeypatch):
    paths = _FakePaths(tmp_path)
    monkeypatch.setattr(startup_sync_module, "get_paths", lambda: paths)

    repo = paths.runtime_root / "repository"
    contaminant = repo / ".git" / "refs" / "heads" / "desktop.ini"
    contaminant.parent.mkdir(parents=True)
    contaminant.write_text("shell metadata", encoding="utf-8")

    provider = _FetchAssertingProvider(contaminant)
    sync = StartupSynchronization(provider)
    sync._preflight_authoritative_database = lambda: True
    sync._apply_runtime_database = lambda: True
    sync._refresh_database_sessions = lambda: True

    assert sync.run() is True
    assert provider.calls == ["connect", "fetch", "reset"]
    assert not contaminant.exists()
