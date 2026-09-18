# -*- coding: utf-8 -*-
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional

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
from centermanager.core.git_locator import locate_git


class GitProvider:
    def __init__(self, repo_path: Path, credentials: Optional[GitCredentials] = None, git_executable: Optional[str] = None):
        self._repo_path = repo_path
        self._credentials = credentials
        self._git_executable = git_executable or str(locate_git() or "")
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
        except GitPullFailed:
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
        """Push local commits to remote. Works even if no changes but has pending commits."""
        try:
            if self.has_pending_push():
                self._run_git_command(["push", "origin", self._credentials.branch])
            self._status = GitStatus.CONNECTED
            return True
        except GitNetworkError:
            self._status = GitStatus.OFFLINE
            raise
        except GitPushFailed:
            self._status = GitStatus.ERROR
            raise
        except Exception as e:
            self._status = GitStatus.ERROR
            raise GitException(f"Push failed: {e}")

    def has_pending_push(self) -> bool:
        """Check if local has commits not pushed to remote."""
        if not self._credentials or not self._credentials.repository_url:
            return False
        try:
            local_commit = self._run_git_command(["rev-parse", "HEAD"]).strip()
            remote_ref = f"origin/{self._credentials.branch}"
            try:
                remote_commit = self._run_git_command(["rev-parse", remote_ref]).strip()
            except GitException:
                return True
            return local_commit != remote_commit
        except Exception:
            return False

    def status(self) -> dict:
        # Do not expose repository path or raw Git error details through a
        # status payload that may be rendered by UI/diagnostic surfaces.
        return {
            "status": self._status.value,
            "branch": self._credentials.branch if self._credentials else None,
            "last_error": "Git operation failed" if self._last_error else None,
        }

    def connection_status(self) -> str:
        if self._status == GitStatus.OFFLINE:
            return "OFFLINE"
        elif self._status == GitStatus.ERROR:
            return "ERROR"
        return "ONLINE"

    def is_offline(self) -> bool:
        return self._status in (GitStatus.OFFLINE, GitStatus.ERROR)

    def _run_git_command(self, args: list) -> str:
        if not self._git_executable:
            self._status = GitStatus.ERROR
            self._last_error = "Git executable not found"
            raise GitException("Git executable not found. Configure portable Git or install Git.")
        cmd = [self._git_executable] + args
        env = os.environ.copy()
        if self._credentials and self._credentials.token:
            env["GIT_ASKPASS"] = "echo"
            env["GIT_USER"] = self._credentials.username
            env["GIT_PASSWORD"] = self._credentials.token
        try:
            run_kwargs = {
                "cwd": str(self._repo_path),
                "capture_output": True,
                "text": True,
                "env": env,
                "check": False,
            }
            if os.name == "nt":
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, **run_kwargs)
            if result.returncode != 0:
                stderr = result.stderr
                if "authentication" in stderr.lower() or "authorization" in stderr.lower():
                    raise GitAuthenticationFailed("Git authentication failed")
                elif "not found" in stderr.lower() or "does not exist" in stderr.lower():
                    raise GitRepositoryNotFound("Git repository was not found")
                elif "merge conflict" in stderr.lower() or "need to pull" in stderr.lower():
                    raise GitMergeRequired("Git merge is required")
                elif "pull" in cmd and "failed" in stderr.lower():
                    raise GitPullFailed("Git pull failed")
                elif "push" in cmd and "failed" in stderr.lower():
                    raise GitPushFailed("Git push failed")
                elif "could not read from remote" in stderr.lower() or "network" in stderr.lower():
                    raise GitNetworkError("Git network operation failed")
                else:
                    raise GitException("Git command failed")
            return result.stdout
        except subprocess.CalledProcessError:
            raise GitException("Git command execution failed")
        except FileNotFoundError:
            self._status = GitStatus.ERROR
            self._last_error = "Git executable not found"
            raise GitException("Git executable not found in PATH.")
