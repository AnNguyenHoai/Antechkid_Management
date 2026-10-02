# -*- coding: utf-8 -*-
"""Regression tests for GitConfigService connection-test authentication."""

from pathlib import Path
from types import SimpleNamespace

import centermanager.services.git_config_service as git_config_service
from centermanager.services.git_config_service import GitConfig, GitConfigService


REPOSITORY_URL = "https://github.com/AnTechKids/example.git"
USERNAME = "antechkids-service"
TOKEN = "test-secret-token"


def _config(token: str = TOKEN) -> GitConfig:
    return GitConfig(
        repository_url=REPOSITORY_URL,
        username=USERNAME,
        token=token,
        branch="main_repos",
    )


def test_windows_connection_test_isolates_host_credentials_and_uses_app_auth(monkeypatch, tmp_path):
    """A host Git account/helper must not become the credential source."""
    captured = {}

    monkeypatch.setattr(git_config_service.sys, "platform", "win32")
    monkeypatch.setattr(git_config_service, "locate_git", lambda: Path("C:/portable-git/bin/git.exe"))
    monkeypatch.setattr(
        git_config_service,
        "hidden_subprocess_kwargs",
        lambda: {"creationflags": 0x08000000},
    )

    # Simulate process-local Git config inherited from a machine/user profile.
    # test_connection() must replace it with the CenterManager hardening entries.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "credential.helper")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "manager-core")

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="deadbeef\tHEAD\n", stderr="")

    monkeypatch.setattr(git_config_service.subprocess, "run", fake_run)

    service = GitConfigService(config_path=tmp_path / "config.json")
    assert service.test_connection(_config()) is True

    args = captured["args"]
    env = captured["kwargs"]["env"]

    assert args == ["C:/portable-git/bin/git.exe", "ls-remote", REPOSITORY_URL, "HEAD"]
    assert TOKEN not in " ".join(args)
    assert USERNAME not in " ".join(args)

    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert env["GIT_CONFIG_VALUE_0"] == ""
    assert env["GIT_CONFIG_KEY_1"] == "core.askpass"
    assert env["GIT_CONFIG_VALUE_1"] == ""
    assert env["GIT_CONFIG_KEY_2"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_2"].startswith("Authorization: Basic ")
    assert TOKEN not in env["GIT_CONFIG_VALUE_2"]
    assert captured["kwargs"]["creationflags"] == 0x08000000


def test_windows_connection_test_clean_host_still_injects_app_auth(monkeypatch, tmp_path):
    """A clean Windows PC must authenticate without Git Credential Manager."""
    captured = {}

    monkeypatch.setattr(git_config_service.sys, "platform", "win32")
    monkeypatch.setattr(git_config_service, "locate_git", lambda: Path("git.exe"))
    monkeypatch.setattr(git_config_service, "hidden_subprocess_kwargs", lambda: {})
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="deadbeef\tHEAD\n", stderr="")

    monkeypatch.setattr(git_config_service.subprocess, "run", fake_run)

    service = GitConfigService(config_path=tmp_path / "config.json")
    assert service.test_connection(_config()) is True

    assert captured["env"]["GIT_CONFIG_KEY_2"] == "http.extraHeader"
    assert captured["env"]["GIT_CONFIG_VALUE_2"].startswith("Authorization: Basic ")
    assert TOKEN not in " ".join(captured["args"])


def test_windows_connection_test_without_token_remains_non_interactive(monkeypatch, tmp_path):
    captured = {}

    monkeypatch.setattr(git_config_service.sys, "platform", "win32")
    monkeypatch.setattr(git_config_service, "locate_git", lambda: Path("git.exe"))
    monkeypatch.setattr(git_config_service, "hidden_subprocess_kwargs", lambda: {})

    def fake_run(args, **kwargs):
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=1, stdout="", stderr="authentication required")

    monkeypatch.setattr(git_config_service.subprocess, "run", fake_run)

    service = GitConfigService(config_path=tmp_path / "config.json")
    assert service.test_connection(_config(token="")) is False

    env = captured["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert env["GIT_CONFIG_VALUE_0"] == ""
    assert env["GIT_CONFIG_VALUE_1"] == ""
    assert "http.extraHeader" not in {
        env.get("GIT_CONFIG_KEY_0"),
        env.get("GIT_CONFIG_KEY_1"),
    }


def test_non_windows_connection_test_retains_secret_free_askpass(monkeypatch, tmp_path):
    """The Windows hardening change must not remove the POSIX AskPass path."""
    captured = {}

    monkeypatch.setattr(git_config_service.sys, "platform", "linux")
    monkeypatch.setattr(git_config_service, "locate_git", lambda: Path("/usr/bin/git"))
    monkeypatch.setattr(git_config_service, "hidden_subprocess_kwargs", lambda: {})
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)

    def fake_run(args, **kwargs):
        captured["env"] = kwargs["env"].copy()
        return SimpleNamespace(returncode=0, stdout="deadbeef\tHEAD\n", stderr="")

    monkeypatch.setattr(git_config_service.subprocess, "run", fake_run)

    service = GitConfigService(config_path=tmp_path / "config.json")
    assert service.test_connection(_config()) is True

    env = captured["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_ASKPASS"]
    assert env["CENTERMANAGER_GIT_USERNAME"] == USERNAME
    assert env["CENTERMANAGER_GIT_TOKEN"] == TOKEN
    assert "http.extraHeader" not in {
        value for key, value in env.items() if key.startswith("GIT_CONFIG_KEY_")
    }
