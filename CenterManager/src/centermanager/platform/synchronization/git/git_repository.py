import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from centermanager.core.git_locator import locate_git
from .git_credential_helper import GitCredentialHelper
from .git_credentials import GitCredentials
from .git_exceptions import (
    GitAuthenticationError,
    GitError,
    GitMergeRequiredError,
    GitNetworkError,
    GitPullError,
    GitPushError,
    GitRepositoryNotFound,
)

logger = logging.getLogger(__name__)


class GitRepository:
    def __init__(self, repo_path: Path, credentials: GitCredentials, git_executable: Optional[str] = None):
        self._repo_path = repo_path
        self._credentials = credentials
        self._git_executable = git_executable or str(locate_git() or "")
        self._ensure_repo()

    def _ensure_repo(self) -> None:
        """Initialize or open repository."""
        git_dir = self._repo_path / ".git"
        if not git_dir.exists():
            self._clone_repo()

    def _clone_repo(self) -> None:
        """Clone repository from remote without embedding credentials in argv."""
        try:
            cmd = [self._git_command(), "clone", self._credentials.repository_url, str(self._repo_path)]
            self._run_cmd(cmd)
            if self._credentials.branch != "main":
                self._checkout_branch()
        except Exception as exc:
            safe_error = self._sanitize_text(str(exc))
            raise GitRepositoryNotFound(f"Failed to clone repository: {safe_error}") from exc

    def _git_command(self) -> str:
        if not self._git_executable:
            raise GitError("Git executable not found. Configure portable Git or install Git.")
        return self._git_executable

    def _git_environment(self) -> tuple[dict, Optional[GitCredentialHelper]]:
        env = os.environ.copy()
        helper = None
        if self._credentials and self._credentials.token:
            helper = GitCredentialHelper(self._credentials.username, self._credentials.token)
            env.update(helper.setup_environment())
        else:
            env["GIT_TERMINAL_PROMPT"] = "0"
        return env, helper

    def _run_cmd(self, cmd: list, cwd: Optional[Path] = None) -> str:
        """Run Git with secrets excluded from command-line arguments."""
        if cwd is None:
            cwd = self._repo_path
        env, helper = self._git_environment()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            if result.returncode != 0:
                error_msg = self._sanitize_text(result.stderr.strip())
                logger.error("Git command failed: %s - %s", self._redact_command(cmd), error_msg)
                self._handle_error(cmd[1] if len(cmd) > 1 else cmd[0], error_msg)
            return result.stdout.strip()
        except subprocess.SubprocessError as exc:
            raise GitNetworkError(f"Git command execution failed: {self._sanitize_text(str(exc))}") from exc
        finally:
            if helper is not None:
                helper.cleanup()

    def _sanitize_text(self, value: str) -> str:
        token = getattr(self._credentials, "token", "") or ""
        if token:
            value = value.replace(token, "***")
        return value

    @staticmethod
    def _redact_command(cmd: list) -> str:
        """Redact embedded credentials before writing Git commands to logs."""
        redacted = []
        for item in cmd:
            value = str(item)
            if "://" in value and "@" in value:
                protocol, rest = value.split("://", 1)
                host_part = rest.split("@", 1)[-1]
                value = f"{protocol}://***@{host_part}"
            redacted.append(value)
        return " ".join(redacted)

    def _handle_error(self, cmd: str, error_msg: str) -> None:
        lower = error_msg.lower()
        if "authentication" in lower or "authorization" in lower or "401" in lower or "403" in lower:
            raise GitAuthenticationError("Git authentication failed")
        if "not found" in lower or "does not exist" in lower:
            raise GitRepositoryNotFound(error_msg)
        if "merge conflict" in lower or "need to pull" in lower:
            raise GitMergeRequiredError(error_msg)
        if cmd == "pull" and "failed" in lower:
            raise GitPullError(error_msg)
        if cmd == "push" and "failed" in lower:
            raise GitPushError(error_msg)
        raise GitError(error_msg)

    def _checkout_branch(self) -> None:
        self._run_cmd([self._git_command(), "checkout", self._credentials.branch])

    def fetch(self) -> bool:
        try:
            self._run_cmd([self._git_command(), "fetch", "origin"])
            return True
        except GitError as exc:
            logger.error("Fetch failed: %s", self._sanitize_text(str(exc)))
            return False

    def pull(self) -> bool:
        try:
            self._run_cmd([self._git_command(), "pull", "origin", self._credentials.branch])
            return True
        except GitError as exc:
            logger.error("Pull failed: %s", self._sanitize_text(str(exc)))
            return False

    def commit(self, message: str) -> bool:
        try:
            self._run_cmd([self._git_command(), "add", "."])
            self._run_cmd([self._git_command(), "commit", "-m", message])
            return True
        except GitError as exc:
            logger.error("Commit failed: %s", self._sanitize_text(str(exc)))
            return False

    def push(self) -> bool:
        try:
            self._run_cmd([self._git_command(), "push", "origin", self._credentials.branch])
            return True
        except GitError as exc:
            logger.error("Push failed: %s", self._sanitize_text(str(exc)))
            return False

    def current_commit(self) -> Optional[str]:
        try:
            output = self._run_cmd([self._git_command(), "rev-parse", "HEAD"])
            return output[:7] if output else None
        except GitError:
            return None

    def current_branch(self) -> Optional[str]:
        try:
            output = self._run_cmd([self._git_command(), "rev-parse", "--abbrev-ref", "HEAD"])
            return output if output else None
        except GitError:
            return None

    def status(self) -> Dict[str, Any]:
        try:
            output = self._run_cmd([self._git_command(), "status", "--porcelain"])
            changes = [line for line in output.split("\n") if line.strip()] if output else []
            return {
                "is_clean": len(changes) == 0,
                "changes": changes,
                "commit": self.current_commit(),
                "branch": self.current_branch(),
            }
        except GitError:
            return {
                "is_clean": False,
                "error": "Git operation failed",
                "commit": None,
                "branch": None,
            }

    def validate(self) -> bool:
        try:
            self._run_cmd([self._git_command(), "status"])
            return True
        except GitError:
            return False
