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

    def init_repository(self) -> None:
        """Initialize or clone repository."""
        if not self._credentials.repository_url:
            raise GitConfigurationError("Repository URL is required.")
        if not self._credentials.token:
            raise GitConfigurationError("Git token is required.")

        if not self._repo_path.exists():
            self._repo_path.mkdir(parents=True, exist_ok=True)
            # Clone
            self._run_git_command(["clone", self._credentials.repository_url, str(self._repo_path)])
        else:
            # Ensure we are in the repo
            self._run_git_command(["status"], check=True)  # just to verify

        # Set user config
        if self._credentials.username:
            self._run_git_command(["config", "user.name", self._credentials.username])
        if self._credentials.email:
            self._run_git_command(["config", "user.email", self._credentials.email])

    def fetch(self) -> bool:
        """Fetch from remote."""
        try:
            self._run_git_command(["fetch", "origin", self._credentials.branch])
            return True
        except GitNetworkError as e:
            self._status = GitStatus.OFFLINE
            raise
        except GitAuthenticationFailed as e:
            self._status = GitStatus.ERROR
            raise
        except Exception as e:
            self._status = GitStatus.ERROR
            raise GitException(f"Fetch failed: {e}")

    def pull(self) -> bool:
        """Pull latest changes."""
        try:
            self._run_git_command(["pull", "origin", self._credentials.branch])
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
        """Commit changes."""
        try:
            self._run_git_command(["add", "."])
            self._run_git_command(["commit", "-m", f"{user}: {message}"])
            return True
        except Exception as e:
            raise GitException(f"Commit failed: {e}")

    def push(self) -> bool:
        """Push to remote."""
        try:
            self._run_git_command(["push", "origin", self._credentials.branch])
            return True
        except GitNetworkError:
            self._status = GitStatus.OFFLINE
            raise
        except GitPushFailed as e:
            self._status = GitStatus.ERROR
            raise
        except Exception as e:
            self._status = GitStatus.ERROR
            raise GitException(f"Push failed: {e}")

    def status(self) -> dict:
        return {
            "status": self._status.value,
            "repo_path": str(self._repo_path),
            "branch": self._credentials.branch if self._credentials else None,
        }

    def _run_git_command(self, args: list) -> str:
        """Run git command with proper authentication."""
        cmd = ["git"] + args
        env = os.environ.copy()
        if self._credentials and self._credentials.token:
            # Set token for authentication
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
                stderr = result.stderr.lower()
                if "fatal: repository" in stderr or "not found" in stderr:
                    raise GitRepositoryNotFound(result.stderr)
                elif "authentication" in stderr:
                    raise GitAuthenticationFailed(result.stderr)
                elif "pull" in cmd and "merge" in stderr:
                    raise GitMergeRequired(result.stderr)
                elif "push" in cmd and "rejected" in stderr:
                    raise GitPushFailed(result.stderr)
                elif "network" in stderr or "unreachable" in stderr:
                    raise GitNetworkError(result.stderr)
                else:
                    raise GitException(result.stderr)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise GitException(f"Git command failed: {e}")
        except FileNotFoundError:
            raise GitException("Git executable not found in PATH.")