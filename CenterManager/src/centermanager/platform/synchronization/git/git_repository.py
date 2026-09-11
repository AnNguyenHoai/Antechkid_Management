import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from .git_credentials import GitCredentials
from .git_exceptions import (
    GitError,
    GitRepositoryNotFound,
    GitAuthenticationError,
    GitPullError,
    GitPushError,
    GitMergeRequiredError,
    GitNetworkError,
)

logger = logging.getLogger(__name__)

class GitRepository:
    def __init__(self, repo_path: Path, credentials: GitCredentials):
        self._repo_path = repo_path
        self._credentials = credentials
        self._ensure_repo()

    def _ensure_repo(self) -> None:
        """Initialize or open repository."""
        git_dir = self._repo_path / ".git"
        if not git_dir.exists():
            # Clone if not exists
            self._clone_repo()

    def _clone_repo(self) -> None:
        """Clone repository from remote."""
        try:
            cmd = ["git", "clone", self._credentials.repository_url, str(self._repo_path)]
            # Add token authentication if provided
            if self._credentials.token:
                # Use token in URL (GitHub/GitLab style)
                url = self._credentials.repository_url
                if "://" in url:
                    protocol, rest = url.split("://", 1)
                    if "@" in rest:
                        # Already has auth? Replace
                        rest = rest.split("@")[-1]
                    url = f"{protocol}://{self._credentials.token}@{rest}"
                    cmd = ["git", "clone", url, str(self._repo_path)]
            self._run_cmd(cmd)
            # Set branch if not default
            if self._credentials.branch != "main":
                # Try to checkout branch after clone
                self._checkout_branch()
        except Exception as e:
            raise GitRepositoryNotFound(f"Failed to clone repository: {e}")

    def _run_cmd(self, cmd: list, cwd: Optional[Path] = None) -> str:
        """Run git command and return output."""
        if cwd is None:
            cwd = self._repo_path
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"Git command failed: {' '.join(cmd)} - {error_msg}")
                self._handle_error(cmd[0], error_msg)
            return result.stdout.strip()
        except subprocess.SubprocessError as e:
            raise GitNetworkError(f"Git command execution failed: {e}")

    def _handle_error(self, cmd: str, error_msg: str) -> None:
        if "Authentication" in error_msg or "authorization" in error_msg:
            raise GitAuthenticationError(error_msg)
        elif "not found" in error_msg or "does not exist" in error_msg:
            raise GitRepositoryNotFound(error_msg)
        elif "merge conflict" in error_msg or "need to pull" in error_msg:
            raise GitMergeRequiredError(error_msg)
        elif "pull" in cmd and "failed" in error_msg:
            raise GitPullError(error_msg)
        elif "push" in cmd and "failed" in error_msg:
            raise GitPushError(error_msg)
        else:
            raise GitError(error_msg)

    def _checkout_branch(self) -> None:
        cmd = ["git", "checkout", self._credentials.branch]
        self._run_cmd(cmd)

    def fetch(self) -> bool:
        try:
            cmd = ["git", "fetch", "origin"]
            self._run_cmd(cmd)
            return True
        except GitError as e:
            logger.error(f"Fetch failed: {e}")
            return False

    def pull(self) -> bool:
        try:
            cmd = ["git", "pull", "origin", self._credentials.branch]
            self._run_cmd(cmd)
            return True
        except GitError as e:
            logger.error(f"Pull failed: {e}")
            return False

    def commit(self, message: str) -> bool:
        try:
            # Add all changes
            self._run_cmd(["git", "add", "."])
            # Commit
            self._run_cmd(["git", "commit", "-m", message])
            return True
        except GitError as e:
            logger.error(f"Commit failed: {e}")
            return False

    def push(self) -> bool:
        try:
            cmd = ["git", "push", "origin", self._credentials.branch]
            self._run_cmd(cmd)
            return True
        except GitError as e:
            logger.error(f"Push failed: {e}")
            return False

    def current_commit(self) -> Optional[str]:
        try:
            output = self._run_cmd(["git", "rev-parse", "HEAD"])
            return output[:7] if output else None
        except GitError:
            return None

    def current_branch(self) -> Optional[str]:
        try:
            output = self._run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            return output if output else None
        except GitError:
            return None

    def status(self) -> Dict[str, Any]:
        try:
            output = self._run_cmd(["git", "status", "--porcelain"])
            changes = []
            if output:
                for line in output.split("\n"):
                    if line.strip():
                        changes.append(line)
            return {
                "is_clean": len(changes) == 0,
                "changes": changes,
                "commit": self.current_commit(),
                "branch": self.current_branch(),
            }
        except GitError as e:
            return {
                "is_clean": False,
                "error": str(e),
                "commit": None,
                "branch": None,
            }

    def validate(self) -> bool:
        try:
            self._run_cmd(["git", "status"])
            return True
        except GitError:
            return False