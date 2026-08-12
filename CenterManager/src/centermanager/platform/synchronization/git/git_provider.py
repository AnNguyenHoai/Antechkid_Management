# -*- coding: utf-8 -*-
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional
import logging

from .git_exceptions import (
    GitException,
    GitRepositoryNotFound,
    GitAuthenticationFailed,
    GitPullFailed,
    GitPushFailed,
    GitMergeRequired,
    GitNetworkError,
    GitCorrupted,
)
from .git_credentials import GitCredentials
from .git_status import GitStatus

logger = logging.getLogger(__name__)


class GitProvider:
    def __init__(self, repo_path: Path, credentials: Optional[GitCredentials] = None):
        self._repo_path = repo_path
        self._credentials = credentials
        self._status = GitStatus.OFFLINE
        self._last_error = None


    def init_repository(self) -> None:
        if not self._credentials.repository_url:
            raise GitConfigurationError("Repository URL is required.")
        if not self._credentials.token:
            raise GitConfigurationError("Git token is required.")

        if not self._repo_path.exists():
            self._repo_path.mkdir(parents=True, exist_ok=True)
            self._run_git_command(["clone", self._credentials.repository_url, str(self._repo_path)])
        else:
            self._run_git_command(["status"])

        if self._credentials.username:
            self._run_git_command(["config", "user.name", self._credentials.username])
        if self._credentials.email:
            self._run_git_command(["config", "user.email", self._credentials.email])

        # ✅ Set status to CONNECTED after successful initialization
        self._status = GitStatus.CONNECTED

    def fetch(self) -> bool:
        try:
            self._run_git_command(["fetch", "origin", self._credentials.branch])
            self._status = GitStatus.CONNECTED
            return True
        except GitNetworkError as e:
            self._status = GitStatus.OFFLINE
            self._last_error = str(e)
            raise
        except GitAuthenticationFailed as e:
            self._status = GitStatus.ERROR
            self._last_error = str(e)
            raise
        except Exception as e:
            self._status = GitStatus.ERROR
            self._last_error = str(e)
            raise GitException(f"Fetch failed: {e}")

    def pull(self) -> bool:
        try:
            self._run_git_command(["pull", "origin", self._credentials.branch])
            self._status = GitStatus.CONNECTED
            return True
        except GitNetworkError:
            self._status = GitStatus.OFFLINE
            raise
        except GitPullFailed as e:
            self._status = GitStatus.ERROR
            raise
        except GitMergeRequired:
            self._status = GitStatus.ERROR
            raise
        except Exception as e:
            self._status = GitStatus.ERROR
            raise GitException(f"Pull failed: {e}")

    def commit(self, message: str, user: str) -> bool:
        try:
            self._run_git_command(["add", "."])
            self._run_git_command(["commit", "-m", f"{user}: {message}"])
            return True
        except Exception as e:
            raise GitException(f"Commit failed: {e}")

    def push(self) -> bool:
        try:
            self._run_git_command(["push", "origin", self._credentials.branch])
            self._status = GitStatus.CONNECTED
            return True
        except GitNetworkError as e:
            self._status = GitStatus.OFFLINE
            logger.error(f"Push failed: Network error - {e}")
            raise
        except GitPushFailed as e:
            self._status = GitStatus.ERROR
            logger.error(f"Push failed: {e}")
            raise
        except Exception as e:
            self._status = GitStatus.ERROR
            logger.exception(f"Push failed: {e}")
            raise GitException(f"Push failed: {e}")

    def status(self) -> dict:
        return {
            "status": self._status.value,
            "repo_path": str(self._repo_path),
            "branch": self._credentials.branch if self._credentials else None,
            "last_error": self._last_error,
        }

    def connection_status(self) -> str:
        """Return simplified connection status: ONLINE, OFFLINE, ERROR."""
        if self._status == GitStatus.OFFLINE:
            return "OFFLINE"
        elif self._status == GitStatus.ERROR:
            return "ERROR"
        return "ONLINE"

    def is_offline(self) -> bool:
        return self._status in (GitStatus.OFFLINE, GitStatus.ERROR)

    def _run_git_command(self, args: list) -> str:
        cmd = ["git"] + args
        env = os.environ.copy()
        if self._credentials and self._credentials.token:
            env["GIT_ASKPASS"] = "echo"
            env["GIT_USER"] = self._credentials.username
            env["GIT_PASSWORD"] = self._credentials.token
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._repo_path),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr
                logger.error(f"Git command failed: {' '.join(cmd)}")
                logger.error(f"stderr: {stderr}")
                # ... existing error handling ...
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.exception(f"Git command execution failed: {e}")
            raise GitException(f"Git command failed: {e}")
        except FileNotFoundError:
            self._status = GitStatus.ERROR
            self._last_error = "Git executable not found"
            logger.error("Git executable not found in PATH.")
            raise GitException("Git executable not found in PATH.")