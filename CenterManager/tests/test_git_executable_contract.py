# -*- coding: utf-8 -*-
"""A3 Git executable contract and standalone startup safety tests."""

from pathlib import Path

import pytest

from centermanager.platform.deployment import git_locator
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials


def test_git_locator_returns_none_when_no_git(monkeypatch, tmp_path):
    monkeypatch.setattr(git_locator.shutil, "which", lambda name: None)
    monkeypatch.setattr(git_locator.sys, "frozen", False, raising=False)
    monkeypatch.setattr(git_locator, "__file__", str(tmp_path / "fake.py"))
    assert git_locator.locate_git() is None


def test_git_provider_does_not_fallback_to_literal_git(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "centermanager.platform.synchronization.git.git_provider.locate_git",
        lambda: None,
    )
    credentials = GitCredentials(
        repository_url="https://example.invalid/repo.git",
        branch="main",
        token="token",
        username="user",
        email="user@example.invalid",
    )
    provider = GitProvider(tmp_path / "repo", credentials)
    with pytest.raises(Exception, match="Git executable not found"):
        provider._run_git_command(["version"])


def test_git_provider_accepts_explicit_executable(tmp_path):
    executable = tmp_path / "git.exe"
    executable.write_text("", encoding="utf-8")
    credentials = GitCredentials("", "main", "", "", "")
    provider = GitProvider(tmp_path / "repo", credentials, git_executable=str(executable))
    assert provider._git_executable == str(executable)


def test_standalone_repository_manager_has_no_git_requirement():
    source = (
        Path(__file__).resolve().parents[1]
        / "src/centermanager/platform/repository/repository_manager.py"
    )
    text = source.read_text(encoding="utf-8")
    assert "GitProvider" not in text
    assert "subprocess" not in text
    assert "locate_git" not in text
