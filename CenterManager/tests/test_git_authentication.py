# -*- coding: utf-8 -*-
"""Tests for Git non-interactive authentication."""

import pytest
import os
import sys
import subprocess
from pathlib import Path

from centermanager.platform.synchronization.git.git_credential_helper import GitCredentialHelper
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


def test_credential_helper_creates_askpass():
    """Verify credential helper creates askpass script."""
    helper = GitCredentialHelper("test_user", "test_token")
    env = helper.setup_environment()
    assert "GIT_ASKPASS" in env
    askpass_path = Path(env["GIT_ASKPASS"])
    assert askpass_path.exists()
    if sys.platform != "win32":
        assert os.access(str(askpass_path), os.X_OK)


def test_credential_helper_returns_token():
    """Verify askpass script returns token when executed."""
    helper = GitCredentialHelper("test_user", "test_token")
    env = helper.setup_environment()
    askpass_path = env["GIT_ASKPASS"]
    result = subprocess.run([askpass_path], capture_output=True, text=True, shell=True)
    assert result.stdout.strip() == "test_token"


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
        username="test_user"
    )
    env = provider._get_env()
    assert env.get("GIT_TERMINAL_PROMPT") == "0"