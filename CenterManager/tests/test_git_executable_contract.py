# -*- coding: utf-8 -*-
"""A3 Git executable contract and standalone startup safety tests."""

from pathlib import Path

import pytest

from centermanager.platform.deployment import git_locator
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


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


def test_sync_provider_marks_offline_when_git_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "centermanager.platform.synchronization.git_synchronization_provider.locate_git",
        lambda: None,
    )
    provider = GitSynchronizationProvider(
        repo_path=tmp_path / "repo",
        repository_url="https://example.invalid/repo.git",
        token="token",
    )
    with pytest.raises(Exception, match="Git executable not found"):
        provider._run_git_command(["version"])
    assert provider.is_offline() is True


def test_git_config_service_fails_connection_test_without_git(monkeypatch):
    from centermanager.services.git_config_service import GitConfigService, GitConfig

    monkeypatch.setattr(
        "centermanager.services.git_config_service.locate_git",
        lambda: None,
    )
    config = GitConfig(
        repository_url="https://example.invalid/repo.git",
        username="user",
        token="token",
    )
    assert GitConfigService().test_connection(config) is False
