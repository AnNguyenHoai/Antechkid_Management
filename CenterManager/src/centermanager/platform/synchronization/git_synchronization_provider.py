# -*- coding: utf-8 -*-
"""GitSynchronizationProvider - Git sync backend implementation with atomic lock."""

import os
import logging
import shutil
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

from .git.git_credential_helper import GitCredentialHelper
from .synchronization_provider import SynchronizationProvider
from .exceptions import (
    AuthenticationFailedError,
    RemoteUnavailableError,
    RepositoryConflictError,
    RepositoryCorruptedError,
    GitNotInstalledError,
    InvalidCredentialsError,
    CloneFailedError,
    FetchFailedError,
    PullFailedError,
    PushFailedError,
)

logger = logging.getLogger(__name__)

try:
    import git
    from git import Repo, GitCommandError, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    logger.warning("GitPython not installed. Git operations will not work.")


class GitSynchronizationProvider(SynchronizationProvider):
    """
    Git synchronization provider with atomic lock using a dedicated lock branch.
    """

    def __init__(
        self,
        repo_path: Path,
        repository_url: str = "",
        token: str = "",
        branch: str = "main",
        username: str = "",
        email: str = "",
    ):
        self._repo_path = Path(repo_path)
        self._repository_url = repository_url
        self._token = token
        self._branch = branch
        self._lock_branch = f"lock-{branch}"  # e.g., lock-main
        self._username = username or os.environ.get("GIT_USER", "CenterManager")
        self._email = email or os.environ.get("GIT_EMAIL", "centermanager@local")
        self._repo: Optional[Repo] = None
        self._connected = False
        self._offline = False
        self._name = "git"
        self._credential_helper: Optional[GitCredentialHelper] = None
        self._askpass_env: dict = {}
        self._lease_duration_seconds = 60

        # A CollaborationPoller runs Git reads in a QThread while the UI/main
        # thread may perform lock or synchronization writes through this same
        # provider. Git commands operating on one working repository must not
        # overlap: concurrent fetch/push/show/ls-remote processes can contend
        # on the repository's .git state and make a refresh appear to hang.
        # RLock is required because higher-level provider methods intentionally
        # compose several _run_git_command() calls.
        self._git_command_lock = threading.RLock()

        if self._token and self._username:
            self._credential_helper = GitCredentialHelper(self._username, self._token)
            self._askpass_env = self._credential_helper.setup_environment()
            logger.info("GitCredentialHelper initialized for non-interactive auth")

        logger.info(f"GitSynchronizationProvider initialized: {repo_path} (branch: {branch}, lock branch: {self._lock_branch})")

    # ===== Core Git operations =====

    def _get_env(self) -> dict:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_COUNT"] = "2"
        env["GIT_CONFIG_KEY_0"] = "credential.helper"
        env["GIT_CONFIG_VALUE_0"] = ""
        env["GIT_CONFIG_KEY_1"] = "core.askpass"
        env["GIT_CONFIG_VALUE_1"] = ""
        env.update(self._askpass_env)
        return env

    def _run_git_command(self, args: list, cwd: Optional[Path] = None, check: bool = True, env: Optional[dict] = None) -> str:
        if cwd is None:
            cwd = self._repo_path
        if env is None:
            env = self._get_env()

        logger.debug(f"Running git: {' '.join(args)}")

        with self._git_command_lock:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

        if result.returncode != 0:
            stderr = result.stderr
            stderr_lower = stderr.lower()
            if check:
                if "authentication" in stderr_lower or "401" in stderr_lower or "403" in stderr_lower:
                    raise AuthenticationFailedError(f"Git authentication failed: {stderr.strip()}")
                if "could not read from remote" in stderr_lower or "remote error" in stderr_lower:
                    raise RemoteUnavailableError(f"Remote unavailable: {stderr.strip()}")
                if "diverg" in stderr_lower or "non-fast-forward" in stderr_lower or "rejected" in stderr_lower:
                    raise RepositoryConflictError(f"Conflict: {stderr.strip()}")
                raise RuntimeError(f"Git command failed: {stderr.strip()}")
            else:
                logger.debug(f"Git command failed (non-fatal): {stderr.strip()}")
                return ""

        return result.stdout.strip()

    def connect(self) -> bool:
        if not GIT_AVAILABLE:
            logger.error("GitPython is not installed")
            self._offline = True
            return False

        try:
            if self._repo_path.exists() and (self._repo_path / ".git").exists():
                self._repo = Repo(self._repo_path)
                if self._repository_url:
                    try:
                        if not self._repo.remotes:
                            self._repo.create_remote('origin', self._repository_url)
                        else:
                            if 'origin' not in [r.name for r in self._repo.remotes]:
                                self._repo.create_remote('origin', self._repository_url)
                    except Exception as e:
                        logger.warning(f"Failed to set remote: {e}")
                logger.info(f"Opened existing repository at {self._repo_path}")
            else:
                self._repo = None
                logger.info("Repository not found locally (will be cloned)")

            self._connected = True
            self._offline = False
            return True

        except InvalidGitRepositoryError:
            logger.error(f"Invalid Git repository at {self._repo_path}")
            self._offline = True
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._offline = True
            return False

    def disconnect(self) -> None:
        self._repo = None
        self._connected = False
        self._offline = True
        logger.info("Git provider disconnected")

    def _build_authenticated_url(self) -> str:
        url = self._repository_url
        if self._token:
            if "://" in url:
                protocol, rest = url.split("://", 1)
                if "@" in rest:
                    rest = rest.split("@")[-1]
                return f"{protocol}://{self._token}@{rest}"
        return url

    # ===== Clone =====

    def clone(self, progress_callback: Optional[Callable] = None) -> bool:
        if not GIT_AVAILABLE:
            raise GitNotInstalledError("GitPython is not installed")

        if not self._repository_url:
            raise InvalidCredentialsError("Repository URL is required")

        auth_url = self._build_authenticated_url()

        self._repo_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cloning repository from {self._repository_url} to {self._repo_path}")

        try:
            if progress_callback:
                progress_callback("clone", f"Cloning from {self._repository_url}", 10)

            self._run_git_command(
                ["clone", auth_url, str(self._repo_path), "--depth", "1", "--branch", self._branch],
                cwd=self._repo_path.parent
            )

            self._repo = Repo(self._repo_path)

            with self._repo.config_writer() as config:
                config.set_value("user", "name", self._username)
                config.set_value("user", "email", self._email)

            if progress_callback:
                progress_callback("clone", "Clone completed", 100)

            self._connected = True
            self._offline = False
            logger.info(f"Repository cloned successfully to {self._repo_path}")
            return True

        except Exception as e:
            logger.error(f"Clone failed: {e}")
            if self._repo_path.exists():
                shutil.rmtree(self._repo_path, ignore_errors=True)
            if isinstance(e, AuthenticationFailedError):
                raise
            raise CloneFailedError(f"Clone failed: {e}")
