# -*- coding: utf-8 -*-
"""GitSynchronizationProvider - Git sync backend implementation."""

import os
import logging
import shutil
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

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
    Git synchronization provider using GitPython.
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
        self._username = username or os.environ.get("GIT_USER", "CenterManager")
        self._email = email or os.environ.get("GIT_EMAIL", "centermanager@local")
        self._repo: Optional[Repo] = None
        self._connected = False
        self._offline = False
        self._name = "git"
        self._credential_helper: Optional[GitCredentialHelper] = None
        self._askpass_env: dict = {}

        if self._token and self._username:
            self._credential_helper = GitCredentialHelper(self._username, self._token)
            self._askpass_env = self._credential_helper.setup_environment()
            logger.info("GitCredentialHelper initialized for non-interactive auth")

        logger.info(f"GitSynchronizationProvider initialized: {repo_path} (branch: {branch})")

    def _get_env(self) -> dict:
        """Get environment variables for Git operations with credentials."""
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_COUNT"] = "2"
        env["GIT_CONFIG_KEY_0"] = "credential.helper"
        env["GIT_CONFIG_VALUE_0"] = ""
        env["GIT_CONFIG_KEY_1"] = "core.askpass"
        env["GIT_CONFIG_VALUE_1"] = ""
        env.update(self._askpass_env)
        return env

    def _run_git_command(self, args: list, cwd: Optional[Path] = None) -> str:
        """
        Run a git command and return stdout as string.
        Raises exception on failure.
        """
        if cwd is None:
            cwd = self._repo_path

        env = self._get_env()
        logger.debug(f"Running git: {' '.join(args)}")

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
            if "authentication" in stderr_lower or "401" in stderr_lower or "403" in stderr_lower:
                logger.error(f"Git authentication failed: {stderr.strip()}")
                raise AuthenticationFailedError("Git authentication failed. Please check your token.")
            if "could not read from remote" in stderr_lower or "remote error" in stderr_lower:
                raise RemoteUnavailableError(f"Remote unavailable: {stderr.strip()}")
            if "diverg" in stderr_lower or "non-fast-forward" in stderr_lower or "rejected" in stderr_lower:
                raise RepositoryConflictError(f"Conflict: {stderr.strip()}")
            raise RuntimeError(f"Git command failed: {stderr.strip()}")

        return result.stdout.strip()

    def connect(self) -> bool:
        """Connect to Git repository."""
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
        """Disconnect from repository."""
        self._repo = None
        self._connected = False
        self._offline = True
        logger.info("Git provider disconnected")

    def _build_authenticated_url(self) -> str:
        """Build authenticated URL if token exists."""
        url = self._repository_url
        if self._token:
            if "://" in url:
                protocol, rest = url.split("://", 1)
                if "@" in rest:
                    rest = rest.split("@")[-1]
                return f"{protocol}://{self._token}@{rest}"
        return url

    def clone(self, progress_callback: Optional[Callable] = None) -> bool:
        """Clone repository from remote."""
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

    def fetch(self) -> bool:
        """Fetch remote metadata."""
        self._ensure_repo()

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found, fetch skipped")
            return True

        try:
            self._run_git_command(["fetch", "origin", self._branch])
            logger.info("Fetch completed successfully")
            return True
        except RemoteUnavailableError:
            logger.warning("Remote unavailable during fetch")
            return False
        except AuthenticationFailedError:
            raise
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            raise FetchFailedError(f"Fetch failed: {e}")

    def pull(self) -> bool:
        """Pull remote changes. If diverged, reset to remote."""
        self._ensure_repo()

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found, pull skipped")
            return True

        try:
            self._run_git_command(["fetch", "origin", self._branch])

            local_commit = self._run_git_command(["rev-parse", "HEAD"])
            try:
                remote_commit = self._run_git_command(["rev-parse", f"origin/{self._branch}"])
            except Exception:
                return True

            if local_commit == remote_commit:
                logger.info("Already up to date")
                return True

            # Try fast-forward
            try:
                self._run_git_command(["merge", "--ff-only", f"origin/{self._branch}"])
                logger.info(f"Fast-forwarded to {remote_commit[:8]}")
                return True
            except RepositoryConflictError:
                # Diverged - reset to remote
                logger.warning(f"Diverged: resetting to remote")
                self._run_git_command(["reset", "--hard", f"origin/{self._branch}"])
                logger.info(f"Reset to remote {remote_commit[:8]}")
                return True

        except RepositoryConflictError:
            raise
        except RemoteUnavailableError:
            logger.warning("Remote unavailable during pull")
            return False
        except AuthenticationFailedError:
            raise
        except Exception as e:
            logger.error(f"Pull failed: {e}")
            raise PullFailedError(f"Pull failed: {e}")

    def publish(self, message: str, user: str) -> bool:
        """Commit and push local changes."""
        self._ensure_repo()

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found, cannot publish")
            raise RemoteUnavailableError("No remote origin configured")

        try:
            # Pull latest (will reset if diverged)
            try:
                self.pull()
            except Exception as e:
                logger.warning(f"Pull before publish failed: {e}")

            # Stage all changes with force
            self._run_git_command(["add", "-A"])
            self._run_git_command(["add", "--force", "database/center.db"])
            self._run_git_command(["add", "--force", "manifest.json"])
            if (self._repo_path / "collaboration").exists():
                self._run_git_command(["add", "--force", "collaboration/"])

            status_out = self._run_git_command(["status", "--porcelain"])
            if status_out:
                logger.info(f"Git status changes:\n{status_out}")
            else:
                logger.warning("Git status shows no changes")

            if status_out:
                commit_message = f"{user}: {message}"
                self._run_git_command(["commit", "-m", commit_message])
                logger.info(f"Committed: {commit_message}")
            else:
                staged_out = self._run_git_command(["diff", "--cached", "--name-only"])
                if staged_out:
                    logger.info(f"Staged changes found:\n{staged_out}")
                    commit_message = f"{user}: {message}"
                    self._run_git_command(["commit", "-m", commit_message])
                    logger.info(f"Committed staged changes: {commit_message}")

            if self._has_pending_push():
                self._push()
                return True
            else:
                try:
                    local_commit = self._run_git_command(["rev-parse", "HEAD"])
                    remote_commit = self._run_git_command(["rev-parse", f"origin/{self._branch}"])
                    if local_commit != remote_commit:
                        logger.info(f"Local differs from remote. Pushing.")
                        self._push()
                        return True
                except Exception:
                    pass
                return True

        except AuthenticationFailedError:
            raise
        except RemoteUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            raise PushFailedError(f"Push failed: {e}")

    def _has_pending_push(self) -> bool:
        """Check if local has commits not pushed to remote."""
        try:
            local_commit = self._run_git_command(["rev-parse", "HEAD"])
            try:
                remote_commit = self._run_git_command(["rev-parse", f"origin/{self._branch}"])
                return local_commit != remote_commit
            except Exception:
                return True
        except Exception:
            return False

    def _push(self) -> None:
        """Push to remote with retry."""
        logger.info("Git push starting (non-interactive mode)")
        auth_url = self._build_authenticated_url()
        push_url = auth_url if auth_url != self._repository_url else self._repository_url

        for attempt in range(3):
            try:
                self._run_git_command(["push", push_url, f"HEAD:{self._branch}"])
                logger.info("Push successful")
                return
            except RepositoryConflictError as e:
                if attempt < 2:
                    logger.warning(f"Push conflict, retrying (attempt {attempt+1}/3): {e}")
                    try:
                        self._run_git_command(["pull", "origin", self._branch, "--rebase"])
                    except Exception:
                        pass
                    continue
                raise
            except Exception as e:
                logger.error(f"Push failed: {e}")
                raise PushFailedError(f"Push failed: {e}")

    def status(self) -> Dict[str, Any]:
        """Return provider status."""
        status = {
            "provider": self._name,
            "connected": self._connected,
            "offline": self._offline,
            "repo_path": str(self._repo_path),
            "branch": self._branch,
            "has_credentials": bool(self._token),
        }
        if self._repo and self._connected:
            try:
                status["current_commit"] = self._run_git_command(["rev-parse", "HEAD"])[:8]
                status["is_dirty"] = bool(self._run_git_command(["status", "--porcelain"]))
            except Exception:
                pass
        return status

    def remote_manifest(self) -> Optional[Dict[str, Any]]:
        """Get remote manifest without merging."""
        if not self._connected or self._repo is None:
            return None
        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found, remote_manifest skipped")
            return None

        try:
            self._run_git_command(["fetch", "origin", self._branch])
            result = self._run_git_command(["show", f"origin/{self._branch}:manifest.json"])
            manifest = json.loads(result)
            logger.info(f"Remote manifest version: {manifest.get('runtime_version', 0)}")
            return manifest
        except json.JSONDecodeError:
            logger.warning("manifest.json does not exist on remote or is invalid")
            return None
        except RemoteUnavailableError:
            logger.warning("Remote unavailable for manifest")
            return None
        except AuthenticationFailedError:
            raise
        except Exception as e:
            logger.error(f"Failed to get remote manifest: {e}")
            return None

    def current_version(self) -> int:
        """Get current runtime version from local manifest."""
        manifest_path = self._repo_path / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("runtime_version", 0)
            except Exception:
                return 0
        return 0

    def update_manifest(self, version: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update manifest.json in repository with new version."""
        manifest_path = self._repo_path / "manifest.json"
        try:
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {
                    "schema_version": 1,
                    "runtime_version": 0,
                    "database_version": 1,
                    "minimum_app_version": "0.1.0",
                    "publisher": "CenterManager",
                    "branch": self._branch,
                    "created_at": datetime.now().isoformat(),
                    "published_at": None,
                }

            data["runtime_version"] = version
            data["published_at"] = datetime.now().isoformat()
            if metadata:
                data.update(metadata)

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            logger.info(f"Manifest updated to version {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")
            return False

    def health(self) -> bool:
        """Check provider health."""
        if not GIT_AVAILABLE:
            return False
        if not self._connected:
            return False
        try:
            if not self._repo or not self._repo_path.exists():
                return False
            self._run_git_command(["version"])
            try:
                self._run_git_command(["fetch", "origin", "--dry-run"])
                self._offline = False
            except Exception:
                self._offline = True
                return self._repo_path.exists()
            return True
        except Exception:
            return False

    def name(self) -> str:
        return self._name

    def is_offline(self) -> bool:
        return self._offline or not self._connected

    def validate(self) -> bool:
        """Validate provider configuration."""
        if not GIT_AVAILABLE:
            return False
        if not self._repo_path.exists():
            return False
        if not (self._repo_path / ".git").exists():
            return False
        if self._repo:
            try:
                result = self._run_git_command(["branch"])
                branches = [b.strip().replace("*", "").strip() for b in result.split("\n") if b.strip()]
                if self._branch not in branches:
                    logger.warning(f"Branch {self._branch} not found in local repo")
                    return False
            except Exception:
                return False
        return True

    def is_configured(self) -> bool:
        return bool(self._repository_url)

    def reset_to_remote(self, branch: Optional[str] = None) -> bool:
        """Reset local repository to match remote branch."""
        if branch is None:
            branch = self._branch
        try:
            self._run_git_command(["fetch", "origin"])
            self._run_git_command(["reset", "--hard", f"origin/{branch}"])
            logger.info(f"Reset local repository to origin/{branch}")
            return True
        except Exception as e:
            logger.exception(f"Reset to remote failed: {e}")
            return False

    # ============ LOCK METHODS ============

    def acquire_lock(self, lock_data: dict) -> bool:
        """
        Atomic lock acquisition using Git.
        Returns True if lock acquired, False otherwise.
        """
        lock_path = self._repo_path / "collaboration" / "lock.json"
        try:
            # 1. Fetch latest
            self._run_git_command(["fetch", "origin"])

            # 2. Check if lock exists on remote
            try:
                remote_lock_content = self._run_git_command(["show", f"origin/{self._branch}:collaboration/lock.json"])
                remote_lock = json.loads(remote_lock_content)
                if remote_lock.get("locked", False):
                    last_hb = remote_lock.get("last_heartbeat")
                    if last_hb:
                        try:
                            hb_time = datetime.fromisoformat(last_hb)
                            if (datetime.now() - hb_time).total_seconds() <= 60:
                                logger.info("Lock is already held on remote")
                                return False
                            else:
                                logger.warning("Stale lock detected, overriding")
                        except:
                            pass
                    else:
                        logger.warning("Lock has no heartbeat, overriding")
            except Exception:
                logger.info("No lock found on remote, safe to acquire")

            # 3. Write new lock file locally
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with open(lock_path, 'w') as f:
                json.dump(lock_data, f, indent=2)

            # 4. Stage and commit
            self._run_git_command(["add", "collaboration/lock.json"])
            self._run_git_command(["commit", "-m", f"Lock acquired by {lock_data.get('owner')}"])

            # 5. Pull rebase to catch any remote changes before push
            try:
                self._run_git_command(["pull", "origin", self._branch, "--rebase"])
            except Exception as e:
                logger.error(f"Pull rebase failed during lock acquisition: {e}")
                self._run_git_command(["reset", "--hard", "HEAD~1"])
                return False

            # 6. Push
            try:
                self._run_git_command(["push", "origin", self._branch])
                logger.info("Lock pushed successfully")
                return True
            except RepositoryConflictError as e:
                logger.warning(f"Push conflict during lock acquisition: {e}")
                self._run_git_command(["reset", "--hard", "HEAD~1"])
                return False
            except Exception as e:
                logger.error(f"Push failed during lock acquisition: {e}")
                self._run_git_command(["reset", "--hard", "HEAD~1"])
                return False

        except Exception as e:
            logger.exception(f"Acquire lock failed: {e}")
            return False

    def release_lock(self, owner: str) -> bool:
        """Release lock by removing lock.json and pushing."""
        lock_path = self._repo_path / "collaboration" / "lock.json"
        try:
            if not lock_path.exists():
                return True
            with open(lock_path, 'r') as f:
                data = json.load(f)
            if data.get("owner") != owner:
                logger.warning(f"Lock owner mismatch: {data.get('owner')} != {owner}")
                return False

            lock_path.unlink()
            self._run_git_command(["add", "collaboration/lock.json"])
            self._run_git_command(["commit", "-m", f"Lock released by {owner}"])

            # Pull rebase trước khi push
            try:
                self._run_git_command(["pull", "origin", self._branch, "--rebase"])
            except Exception as e:
                logger.error(f"Pull rebase failed during release: {e}")
                self._run_git_command(["reset", "--hard", "HEAD~1"])
                return False

            try:
                self._run_git_command(["push", "origin", self._branch])
                logger.info("Lock released and pushed successfully")
                return True
            except RepositoryConflictError as e:
                logger.warning(f"Push conflict during lock release: {e}")
                self._run_git_command(["reset", "--hard", "HEAD~1"])
                return False
            except Exception as e:
                logger.error(f"Push failed during lock release: {e}")
                self._run_git_command(["reset", "--hard", "HEAD~1"])
                return False

        except Exception as e:
            logger.exception(f"Release lock failed: {e}")
            return False

    def _ensure_repo(self):
        """Ensure repository is available."""
        if not self._connected:
            raise RuntimeError("Git provider not connected. Call connect() first.")
        if self._repo is None:
            raise RuntimeError("Repository not initialized. Call clone() first.")