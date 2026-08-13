# -*- coding: utf-8 -*-
"""GitSynchronizationProvider - Git sync backend implementation."""

import os
import logging
import tempfile
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

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

        logger.info(f"GitSynchronizationProvider initialized: {repo_path} (branch: {branch})")

    def connect(self) -> bool:
        """Connect to Git repository."""
        if not GIT_AVAILABLE:
            logger.error("GitPython is not installed")
            self._offline = True
            return False

        try:
            if self._repo_path.exists() and (self._repo_path / ".git").exists():
                self._repo = Repo(self._repo_path)
                logger.info(f"Opened existing repository at {self._repo_path}")
            else:
                self._repo = None
                logger.info("Repository not found locally (will be cloned)")
                self._connected = True
                self._offline = False
                return True

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

    def clone(self, progress_callback: Optional[Callable] = None) -> bool:
        """Clone repository from remote."""
        if not GIT_AVAILABLE:
            raise GitNotInstalledError("GitPython is not installed")

        if not self._repository_url:
            raise InvalidCredentialsError("Repository URL is required")

        if not self._token:
            raise InvalidCredentialsError("Git token is required")

        auth_url = self._build_authenticated_url()

        self._repo_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cloning repository from {self._repository_url} to {self._repo_path}")

        try:
            if progress_callback:
                progress_callback("clone", f"Cloning from {self._repository_url}", 10)

            self._repo = Repo.clone_from(
                auth_url,
                str(self._repo_path),
                branch=self._branch,
                depth=1,
                progress=None,
            )

            with self._repo.config_writer() as config:
                config.set_value("user", "name", self._username)
                config.set_value("user", "email", self._email)

            if progress_callback:
                progress_callback("clone", "Clone completed", 100)

            self._connected = True
            self._offline = False
            logger.info(f"Repository cloned successfully to {self._repo_path}")
            return True

        except GitCommandError as e:
            logger.error(f"Clone failed: {e}")
            if self._repo_path.exists():
                shutil.rmtree(self._repo_path, ignore_errors=True)

            if "authentication" in str(e).lower() or "403" in str(e) or "401" in str(e):
                raise AuthenticationFailedError(f"Authentication failed: {e}")
            raise CloneFailedError(f"Clone failed: {e}")
        except Exception as e:
            logger.error(f"Clone failed: {e}")
            raise CloneFailedError(f"Clone failed: {e}")

    def fetch(self) -> bool:
        """Fetch remote metadata."""
        self._ensure_repo()

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found")
            return True

        try:
            origin = self._repo.remotes.origin
            origin.fetch()
            logger.info("Fetch completed successfully")
            return True

        except GitCommandError as e:
            logger.error(f"Fetch failed: {e}")
            if "authentication" in str(e).lower():
                raise AuthenticationFailedError(f"Authentication failed: {e}")
            if "could not read from remote repository" in str(e).lower():
                raise RemoteUnavailableError(f"Remote unavailable: {e}")
            raise FetchFailedError(f"Fetch failed: {e}")
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            raise FetchFailedError(f"Fetch failed: {e}")

    def pull(self) -> bool:
        """Pull remote changes (fast-forward only)."""
        self._ensure_repo()

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found")
            return True

        try:
            origin = self._repo.remotes.origin
            origin.fetch()

            remote_ref = f"origin/{self._branch}"
            if remote_ref not in self._repo.refs:
                logger.warning(f"Remote branch {self._branch} not found")
                return True

            current_commit = self._repo.head.commit
            remote_commit = self._repo.refs[remote_ref].commit

            base = self._repo.merge_base(current_commit, remote_commit)

            if len(base) == 0:
                logger.warning("No common ancestor between local and remote")
                raise RepositoryConflictError("No common ancestor between local and remote")

            if current_commit == remote_commit:
                logger.info("Already up to date")
                return True

            if base[0] == current_commit:
                self._repo.head.reference = remote_commit
                self._repo.head.reset(index=True, working_tree=True)
                logger.info(f"Fast-forwarded to {remote_commit.hexsha[:8]}")
                return True
            else:
                logger.warning(f"Diverged: local {current_commit.hexsha[:8]} != remote {remote_commit.hexsha[:8]}")
                raise RepositoryConflictError(
                    f"Local and remote have diverged. Local: {current_commit.hexsha[:8]}, Remote: {remote_commit.hexsha[:8]}"
                )

        except GitCommandError as e:
            logger.error(f"Pull failed: {e}")
            if "authentication" in str(e).lower():
                raise AuthenticationFailedError(f"Authentication failed: {e}")
            raise PullFailedError(f"Pull failed: {e}")
        except RepositoryConflictError:
            raise
        except Exception as e:
            logger.error(f"Pull failed: {e}")
            raise PullFailedError(f"Pull failed: {e}")

    def publish(self, message: str, user: str) -> bool:
        """
        Commit and push local changes.
        Handles:
        A) Working tree dirty -> add, commit, push
        B) Working tree clean but local HEAD ahead of remote -> push only
        C) First push (no remote branch) -> push with set-upstream
        """
        self._ensure_repo()

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found, cannot publish")
            raise RemoteUnavailableError("No remote origin configured")

        try:
            # Case A: Working tree dirty
            if self._repo.is_dirty(untracked_files=True):
                self._repo.git.add(A=True)
                commit_message = f"{user}: {message}"
                self._repo.index.commit(commit_message)
                logger.info(f"Committed: {commit_message}")

            # Case B/C: Check if there are pending commits to push
            if self._has_pending_push():
                self._push()
                return True
            else:
                logger.info("No changes to publish")
                return True

        except GitCommandError as e:
            logger.error(f"Publish failed: {e}")
            if "authentication" in str(e).lower():
                raise AuthenticationFailedError(f"Authentication failed: {e}")
            raise PushFailedError(f"Push failed: {e}")
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            raise PushFailedError(f"Push failed: {e}")

    def _has_pending_push(self) -> bool:
        """Check if local commits are ahead of remote."""
        try:
            # Get local HEAD
            local_commit = self._repo.head.commit.hexsha
            # Check if remote branch exists
            remote_ref = f"origin/{self._branch}"
            if remote_ref not in self._repo.refs:
                # No remote branch, so there is pending push
                return True
            remote_commit = self._repo.refs[remote_ref].commit.hexsha
            return local_commit != remote_commit
        except Exception:
            return True  # Assume pending if we can't determine

    def _push(self) -> None:
        """Push to remote. Handles first push with set-upstream if needed."""
        origin = self._repo.remotes.origin
        # Check if remote branch exists
        remote_ref = f"origin/{self._branch}"
        if remote_ref not in self._repo.refs:
            # First push - set upstream
            refspec = f"{self._branch}:{self._branch}"
            push_info = origin.push(refspec=refspec, set_upstream=True)
        else:
            refspec = f"{self._branch}:{self._branch}"
            push_info = origin.push(refspec=refspec)

        for info in push_info:
            if info.flags & info.ERROR:
                raise PushFailedError(f"Push failed: {info.summary}")
            logger.info(f"Push successful: {info.summary}")

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
                status["current_commit"] = self._repo.head.commit.hexsha[:8]
                status["is_dirty"] = self._repo.is_dirty(untracked_files=True)
                status["branch"] = self._repo.active_branch.name
                status["pending_push"] = self._has_pending_push()
            except Exception:
                pass

        return status

    def remote_manifest(self) -> Optional[Dict[str, Any]]:
        """Get remote manifest without merging."""
        if not self._connected or self._repo is None:
            return None

        if not hasattr(self._repo.remotes, 'origin') or not self._repo.remotes:
            logger.warning("No remote origin found")
            return None

        try:
            origin = self._repo.remotes.origin
            origin.fetch()

            remote_ref = f"origin/{self._branch}"
            if remote_ref not in self._repo.refs:
                logger.warning(f"Remote branch {self._branch} not found")
                return None

            manifest_content = self._repo.git.show(f"{remote_ref}:manifest.json")
            manifest = json.loads(manifest_content)
            logger.info(f"Remote manifest version: {manifest.get('runtime_version', 0)}")
            return manifest

        except GitCommandError as e:
            logger.error(f"Failed to get remote manifest: {e}")
            return None
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
                pass
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

            try:
                self._repo.git.version()
            except Exception:
                return False

            try:
                if hasattr(self._repo.remotes, 'origin') and self._repo.remotes:
                    origin = self._repo.remotes.origin
                    origin.fetch(depth=1, dry_run=True)
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
                branches = [b.name for b in self._repo.branches]
                if self._branch not in branches:
                    logger.warning(f"Branch {self._branch} not found in local repo")
                    return False
            except Exception:
                return False

        return True

    def is_configured(self) -> bool:
        return bool(self._repository_url and self._token)

    def _ensure_repo(self):
        """Ensure repository is available."""
        if not self._connected:
            raise RuntimeError("Git provider not connected. Call connect() first.")
        if self._repo is None:
            raise RuntimeError("Repository not initialized. Call clone() first.")

    def _build_authenticated_url(self) -> str:
        """Build authenticated URL with token."""
        url = self._repository_url
        if "://" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                rest = rest.split("@")[-1]
            return f"{protocol}://{self._token}@{rest}"
        return url