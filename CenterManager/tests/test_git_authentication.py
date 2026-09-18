# -*- coding: utf-8 -*-
"""Tests for Git non-interactive authentication."""

import os
import subprocess
import sys
from pathlib import Path

from centermanager.platform.synchronization.git.git_credential_helper import GitCredentialHelper
from centermanager.platform.synchronization import GitSynchronizationProvider


def test_credential_helper_creates_askpass():
    """Verify credential helper creates a secret-free askpass script."""
    helper = GitCredentialHelper("test_user", "test_token")
    env = helper.setup_environment()
    assert "GIT_ASKPASS" in env
    askpass_path = Path(env["GIT_ASKPASS"])
    assert askpass_path.exists()
    assert "test_token" not in askpass_path.read_text(encoding="utf-8")
    if sys.platform != "win32":
        assert os.access(str(askpass_path), os.X_OK)


def test_credential_helper_returns_token_from_child_environment():
    """Askpass returns the token from env without persisting it in the script."""
    helper = GitCredentialHelper("test_user", "test_token")
    helper_env = helper.setup_environment()
    askpass_path = Path(helper_env["GIT_ASKPASS"])
    process_env = os.environ.copy()
    process_env.update(helper_env)

    if sys.platform == "win32":
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/c", str(askpass_path), "Password"]
    else:
        command = [str(askpass_path), "Password"]

    result = subprocess.run(command, capture_output=True, text=True, env=process_env, check=False)
    assert result.returncode == 0
    assert result.stdout.strip() == "test_token"
    assert "test_token" not in askpass_path.read_text(encoding="utf-8")


def test_credential_helper_cleanup():
    """Verify cleanup removes askpass script."""
    helper = GitCredentialHelper("test_user", "test_token")
    env = helper.setup_environment()
    askpass_path = Path(env["GIT_ASKPASS"])
    assert askpass_path.exists()
    helper.cleanup()
    assert not askpass_path.exists()


def test_environment_has_terminal_prompt_disabled():
    """Verify GIT_TERMINAL_PROMPT is set to 0 in provider environment."""
    provider = GitSynchronizationProvider(
        repo_path=Path("."),
        repository_url="https://example.com",
        token="test_token",
        username="test_user",
    )
    env = provider._get_env()
    assert env.get("GIT_TERMINAL_PROMPT") == "0"
