# -*- coding: utf-8 -*-
"""GitSynchronizationProvider - Git sync backend implementation with atomic lock."""

import os
import logging
import shutil
import json
import subprocess
import tempfile
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

    # ===== Remote lock OID observation =====

    def _remote_lock_oid(self) -> Optional[str]:
        if not self._has_remote_origin():
            return None
        try:
            output = self._run_git_command(
                ["ls-remote", "origin", f"refs/heads/{self._lock_branch}"],
                check=False
            )
            if not output:
                return None
            parts = output.split()
            if len(parts) >= 1:
                return parts[0]
        except Exception as e:
            logger.warning(f"Failed to get remote lock OID: {e}")
        return None

    def _read_lock_from_oid(self, oid: str) -> Dict[str, Any]:
        """
        Read lock.json from a remote lock commit.

        A remote OID returned by `ls-remote` is not necessarily present in this
        client's local object database. This is especially important for a
        second machine observing a lock created by another machine.

        First try the already-local object. If it is missing, fetch only the
        collaboration lock branch and retry. Fetching the lock branch does not
        checkout it and does not modify MAIN HEAD, index, or working tree.
        """
        try:
            content = self._run_git_command(
                ["show", f"{oid}:lock.json"], check=False
            )
            if content:
                return json.loads(content)
        except Exception as e:
            logger.debug(f"Lock OID {oid} not local yet: {e}")

        # The OID came from the remote, but the commit may not exist locally.
        # Fetch the collaboration-only lock branch once, then retry.
        try:
            if self._fetch_lock_branch():
                content = self._run_git_command(
                    ["show", f"{oid}:lock.json"], check=False
                )
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.warning(
                f"Failed to fetch/read remote lock OID {oid}: {e}"
            )

        return {}

    def _has_remote_origin(self) -> bool:
        if not self._repo:
            return False
        try:
            return 'origin' in [r.name for r in self._repo.remotes]
        except Exception:
            return False

    def _fetch_lock_branch(self) -> bool:
        if not self._has_remote_origin():
            return False
        try:
            self._run_git_command(["fetch", "origin", self._lock_branch], check=False)
            return True
        except Exception:
            return False

    def _read_lock_from_branch(self) -> Dict[str, Any]:
        try:
            content = self._run_git_command(["show", f"origin/{self._lock_branch}:lock.json"], check=False)
            if content:
                return json.loads(content)
        except Exception:
            pass
        return {}

    # ===== CRITICAL: _is_lock_valid uses ONLY lease_expires_at =====
    # ===== last_heartbeat is NO LONGER an authority for remote validity =====

    def _is_lock_valid(self, lock_data: Dict[str, Any]) -> bool:
        """
        Check if a remote lock is still valid.
        Authority: lease_expires_at ONLY.
        Locks without lease_expires_at are considered STALE.
        This ensures remote lock validity is decoupled from local heartbeat.
        """
        if not lock_data.get("locked", False):
            return False

        # Primary and ONLY authority: lease_expires_at
        lease_expires_at = lock_data.get("lease_expires_at")
        if lease_expires_at:
            try:
                expires = datetime.fromisoformat(lease_expires_at)
                return datetime.now() < expires
            except Exception:
                pass

        # If lease_expires_at is missing or invalid, treat as stale
        # This ensures legacy locks without lease_expires_at are not considered valid
        logger.debug("Lock missing valid lease_expires_at, treating as stale")
        return False

    # ===== Plumbing-based lock commit creation (no checkout) =====

    def _create_lock_commit_plumbing(self, lock_data: Dict[str, Any], parent_oid: Optional[str] = None) -> Optional[str]:
        """
        Create a commit containing lock.json using Git plumbing.
        Returns commit SHA or None on failure.
        This method does NOT check out lock-main or change HEAD.
        """
        import tempfile
        import os as os_mod
        import shutil

        try:
            # 1. Write lock.json to a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(lock_data, f, indent=2, ensure_ascii=False)
                temp_lock_path = f.name

            # 2. Create blob from the temporary file
            blob_sha = self._run_git_command(["hash-object", "-w", temp_lock_path], check=True).strip()
            os_mod.unlink(temp_lock_path)

            # 3. Create a temporary directory for the index
            temp_dir = tempfile.mkdtemp()
            index_path = os_mod.path.join(temp_dir, "index")

            env = os.environ.copy()
            env["GIT_INDEX_FILE"] = index_path

            # 4. Initialize empty index
            self._run_git_command(["read-tree", "--empty"], env=env, check=True)

            # 5. Add lock.json to the temporary index
            self._run_git_command(
                ["update-index", "--add", "--cacheinfo", "100644", blob_sha, "lock.json"],
                env=env,
                check=True
            )

            # 6. Write tree
            tree_sha = self._run_git_command(["write-tree"], env=env, check=True).strip()

            # 7. Clean up temporary directory
            shutil.rmtree(temp_dir)

            # 8. Create commit
            cmd = ["commit-tree", tree_sha]
            if parent_oid:
                cmd.extend(["-p", parent_oid])
            cmd.extend(["-m", f"Lock acquired by {lock_data.get('owner')}"])
            commit_sha = self._run_git_command(cmd, check=True).strip()

            logger.info(f"Created lock commit: {commit_sha} (parent: {parent_oid or 'none'})")
            return commit_sha

        except Exception as e:
            logger.error(f"Failed to create lock commit via plumbing: {e}")
            return None

    def _push_lock_branch(self, commit_sha: str, expected_oid: Optional[str] = None) -> bool:
        """
        Push a specific commit to the remote lock branch with atomic CAS.
        If expected_oid is None (branch doesn't exist), use normal push to create.
        If expected_oid is provided, use --force-with-lease to ensure atomic.
        """
        if not self._has_remote_origin():
            logger.warning("No remote origin, cannot push lock branch")
            return False
        try:
            if expected_oid is None:
                # Branch doesn't exist remotely; normal push to create
                args = ["push", "origin", f"{commit_sha}:refs/heads/{self._lock_branch}"]
            else:
                # Branch exists; atomic CAS with --force-with-lease
                args = ["push", "origin", f"{commit_sha}:refs/heads/{self._lock_branch}"]
                args.append(f"--force-with-lease={self._lock_branch}:{expected_oid}")
            self._run_git_command(args, check=True)
            logger.info(f"Lock branch pushed successfully: {self._lock_branch}")
            return True
        except RepositoryConflictError:
            logger.warning("Lock branch push failed: remote branch changed (race lost)")
            return False
        except Exception as e:
            logger.error(f"Lock branch push failed: {e}")
            return False

    def _delete_lock_branch(self, expected_oid: Optional[str] = None, force: bool = False) -> bool:
        """Delete the remote lock branch. If force=True, use --force without lease."""
        if not self._has_remote_origin():
            return True
        try:
            if force:
                args = ["push", "origin", "--delete", self._lock_branch, "--force"]
            else:
                args = ["push", "origin", "--delete", self._lock_branch]
                if expected_oid is not None:
                    args.append(f"--force-with-lease={self._lock_branch}:{expected_oid}")
            self._run_git_command(args, check=True)
            logger.info(f"Lock branch deleted: {self._lock_branch}")
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "does not exist" in error_msg or "couldn't find remote ref" in error_msg:
                logger.debug(f"Lock branch already deleted or not found: {e}")
                return True
            logger.warning(f"Failed to delete lock branch: {e}")
            return False

    # ===== Atomic lock operations =====

    def acquire_lock(self, lock_data: dict) -> bool:
        logger.info(f"Atomic lock acquisition started: owner={lock_data.get('owner')}")
        try:
            expected_oid = self._remote_lock_oid()
            if expected_oid is not None:
                # Fetch lock branch to ensure parent OID is available locally
                self._fetch_lock_branch()
                remote_lock = self._read_lock_from_oid(expected_oid)
                if self._is_lock_valid(remote_lock):
                    owner = remote_lock.get("owner", "unknown")
                    logger.info(f"Lock already held by {owner}, acquisition denied")
                    return False

            # Set lease expiry
            lock_data["lease_expires_at"] = (
                datetime.now() + timedelta(seconds=self._lease_duration_seconds)
            ).isoformat()

            # Create lock commit using plumbing (does NOT checkout lock-main)
            commit_sha = self._create_lock_commit_plumbing(lock_data, expected_oid)
            if not commit_sha:
                logger.error("Failed to create lock commit")
                return False

            # Push the commit atomically
            if not self._push_lock_branch(commit_sha, expected_oid):
                logger.error("Failed to push lock branch")
                return False

            # Verify ownership
            new_oid = self._remote_lock_oid()
            if new_oid is not None:
                remote_verify = self._read_lock_from_oid(new_oid)
                if remote_verify.get("session_id") == lock_data.get("session_id"):
                    logger.info(f"Atomic lock acquired successfully: session={lock_data.get('session_id')}")
                    return True
                else:
                    logger.warning("Lock push succeeded but ownership verification failed")
                    return False
            else:
                logger.error("Lock push succeeded but remote OID disappeared")
                return False

        except Exception as e:
            logger.exception(f"Lock acquisition failed: {e}")
            return False

    def release_lock(self, owner: str) -> bool:
        logger.info(f"Atomic lock release requested: owner={owner}")

        try:
            expected_oid = self._remote_lock_oid()
            if expected_oid is None:
                logger.info("No remote lock to release")
                return True

            remote_lock = self._read_lock_from_oid(expected_oid)
            if not remote_lock.get("locked", False):
                remote_owner = remote_lock.get("owner") or remote_lock.get("username")
                if remote_owner == owner or owner == "force_release":
                    pass
                else:
                    return False

            remote_owner = remote_lock.get("owner") or remote_lock.get("username")
            if remote_owner != owner and owner != "force_release":
                logger.warning(f"Lock owner mismatch: remote={remote_owner}, caller={owner}")
                return False

            # Always use deletion (no checkout)
            # First try atomic delete with lease
            if self._delete_lock_branch(expected_oid=expected_oid):
                logger.info(f"Lock released by {owner}")
                return True

            # CAS failed — lock state changed → safe failure
            logger.warning("Atomic delete failed, lock state changed. Not force-deleting.")
            return False

        except Exception as e:
            logger.exception(f"Lock release failed: {e}")
            return False

    def force_release(self, owner: str) -> bool:
        """Administrative force-release of a lock (use with caution)."""
        logger.warning(f"Force release requested by {owner}")
        try:
            if self._delete_lock_branch(force=True):
                logger.info(f"Lock force-released by {owner}")
                return True
            logger.error(f"Force release failed for {owner}")
            return False
        except Exception as e:
            logger.exception(f"Force release exception: {e}")
            return False

    def renew_lock(self, owner: str, session_id: str) -> bool:
        logger.info(f"Lock renewal requested: owner={owner}, session={session_id}")
        try:
            expected_oid = self._remote_lock_oid()
            if expected_oid is None:
                logger.warning("No remote lock to renew")
                return False

            # Fetch lock branch to ensure parent OID is available locally
            self._fetch_lock_branch()

            remote_lock = self._read_lock_from_oid(expected_oid)
            if not remote_lock.get("locked", False):
                logger.warning("Remote lock is not locked")
                return False

            # Validate owner and session
            if remote_lock.get("owner") != owner:
                logger.warning(f"Owner mismatch: remote={remote_lock.get('owner')}, caller={owner}")
                return False

            if remote_lock.get("session_id") != session_id:
                logger.warning(f"Session mismatch: remote={remote_lock.get('session_id')}, caller={session_id}")
                return False

            # Check if lock is still valid using lease_expires_at ONLY
            if not self._is_lock_valid(remote_lock):
                logger.warning("Lock lease expired, cannot renew")
                return False

            # Preserve finishing fields
            finishing_started_at = remote_lock.get("finishing_started_at")
            finishing_deadline = remote_lock.get("finishing_deadline")
            publish_intent = remote_lock.get("publish_intent", False)

            # Build renewed lock data
            renewed_lock = remote_lock.copy()
            renewed_lock["lease_expires_at"] = (
                datetime.now() + timedelta(seconds=self._lease_duration_seconds)
            ).isoformat()

            renewed_lock["finishing_started_at"] = finishing_started_at
            renewed_lock["finishing_deadline"] = finishing_deadline
            renewed_lock["publish_intent"] = publish_intent

            # Create isolated commit
            commit_sha = self._create_lock_commit_plumbing(renewed_lock, expected_oid)
            if not commit_sha:
                logger.error("Failed to create renewal commit")
                return False

            # Push atomically with lease
            if not self._push_lock_branch(commit_sha, expected_oid):
                logger.warning("Renewal push failed: lock state changed")
                return False

            # Verify ownership
            new_oid = self._remote_lock_oid()
            if new_oid is not None:
                remote_verify = self._read_lock_from_oid(new_oid)
                if remote_verify.get("session_id") == session_id:
                    logger.info(f"Lock renewed successfully: session={session_id}")
                    return True
                else:
                    logger.warning("Renewal succeeded but ownership verification failed")
                    return False
            else:
                logger.error("Renewal succeeded but remote OID disappeared")
                return False

        except Exception as e:
            logger.exception(f"Lock renewal failed: {e}")
            return False

    def remote_lock_status(self) -> Dict[str, Any]:
        """
        Get remote lock status including all fields.
        Used for diagnostics, UI, and tests.
        """
        try:
            oid = self._remote_lock_oid()
            if oid is None:
                return {"locked": False, "owner": None, "session_id": None}

            lock_data = self._read_lock_from_oid(oid)
            if not lock_data:
                return {"locked": False, "owner": None, "session_id": None}

            return {
                "locked": lock_data.get("locked", False),
                "owner": lock_data.get("username") or lock_data.get("owner"),
                "session_id": lock_data.get("session_id"),
                "user_id": lock_data.get("user_id"),
                "acquired_at": lock_data.get("acquired_at"),
                "last_heartbeat": lock_data.get("last_heartbeat"),
                "lease_expires_at": lock_data.get("lease_expires_at"),
                "machine": lock_data.get("machine"),
                "finishing_started_at": lock_data.get("finishing_started_at"),
                "finishing_deadline": lock_data.get("finishing_deadline"),
                "publish_intent": lock_data.get("publish_intent", False),
                "lock_generation": lock_data.get("lock_generation", 0),
                "lease_revision": lock_data.get("lease_revision", 0),
            }
        except Exception as e:
            logger.debug(f"Failed to get remote lock status: {e}")
        return {"locked": False, "owner": None, "session_id": None}

    # ===== Other synchronization methods =====

    def fetch(self) -> bool:
        self._ensure_repo()
        if not self._has_remote_origin():
            logger.debug("No remote origin, fetch skipped")
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
            return False

    def pull(self) -> bool:
        self._ensure_repo()
        if not self._has_remote_origin():
            logger.debug("No remote origin, pull skipped")
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
            try:
                self._run_git_command(["merge", "--ff-only", f"origin/{self._branch}"])
                logger.info(f"Fast-forwarded to {remote_commit[:8]}")
                return True
            except RepositoryConflictError:
                logger.warning("Diverged: resetting to remote")
                self._run_git_command(["reset", "--hard", f"origin/{self._branch}"])
                logger.info(f"Reset to remote {remote_commit[:8]}")
                return True
        except Exception as e:
            logger.error(f"Pull failed: {e}")
            return False

    def _has_pending_push(self) -> bool:
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
        if not self._has_remote_origin():
            logger.debug("No remote origin, push skipped")
            return
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

    def _push_only(self, expected_remote_commit: Optional[str] = None) -> None:
        if not self._has_remote_origin():
            logger.debug("No remote origin, push-only skipped")
            return
        auth_url = self._build_authenticated_url()
        push_url = auth_url if auth_url != self._repository_url else self._repository_url
        try:
            push_args = ["push"]
            if expected_remote_commit:
                # MAIN publish fencing: update main only if the remote is still
                # exactly the commit captured when the write transaction began.
                # This is a Git-level CAS; never fall back to an unconditional force push.
                push_args.append(f"--force-with-lease={self._branch}:{expected_remote_commit}")
            push_args.extend([push_url, f"HEAD:{self._branch}"])
            self._run_git_command(push_args)
            logger.info("Push-only successful")
        except RepositoryConflictError as e:
            logger.error(f"Push-only rejected: {e}")
            raise PushFailedError(f"Push rejected: {e}")
        except Exception as e:
            logger.error(f"Push-only failed: {e}")
            raise PushFailedError(f"Push failed: {e}")

    def publish(self, message: str, user: str) -> bool:
        self._ensure_repo()
        try:
            # Pull latest before publishing
            try:
                self.pull()
            except Exception as e:
                logger.warning(f"Pull before publish failed: {e}")

            # Stage business files
            self._run_git_command(["add", "-A"])

            # Force add database (even if .gitignore would ignore it)
            db_path = self._repo_path / "database" / "center.db"
            if db_path.exists():
                self._run_git_command(["add", "--force", "database/center.db"])

            # Force add manifest
            manifest_path = self._repo_path / "manifest.json"
            if manifest_path.exists():
                self._run_git_command(["add", "--force", "manifest.json"])

            # 🔒 COLLABORATION STATE ISOLATION:
            # collaboration/ is NEVER staged. It lives in runtime/collaboration/
            # outside the MAIN working tree. Do NOT add it here.

            # Check if there are changes to commit
            status_out = self._run_git_command(["status", "--porcelain"])
            if status_out:
                commit_message = f"{user}: {message}"
                self._run_git_command(["commit", "-m", commit_message])
                logger.info(f"Committed: {commit_message}")
            else:
                # Check if there are staged changes
                staged_out = self._run_git_command(["diff", "--cached", "--name-only"])
                if staged_out:
                    commit_message = f"{user}: {message}"
                    self._run_git_command(["commit", "-m", commit_message])
                    logger.info(f"Committed staged changes: {commit_message}")

            # Push if there are pending commits
            if self._has_pending_push():
                self._push()
                return True
            return True
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            raise PushFailedError(f"Push failed: {e}")

    def publish_only(self, message: str, user: str, expected_main_commit: Optional[str] = None) -> bool:
        """Publish prepared business changes without any remote synchronization.

        When ``expected_main_commit`` is supplied, the final MAIN push is fenced
        with ``--force-with-lease`` so a remote MAIN change cannot be overwritten.
        A conflict is a terminal publish failure for this attempt; this method
        never pulls/rebases/merges or retries the same stale push.
        """
        self._ensure_repo()
        try:
            if expected_main_commit:
                # Observe the authoritative remote ref directly.  Do not use
                # origin/main here because that would require a fetch and would
                # violate the publish-only contract.
                remote_out = self._run_git_command(
                    ["ls-remote", "origin", f"refs/heads/{self._branch}"]
                )
                remote_main = remote_out.split()[0] if remote_out.strip() else None
                if remote_main != expected_main_commit:
                    raise RepositoryConflictError(
                        f"MAIN changed before publish: expected {expected_main_commit[:8]}, "
                        f"remote is {(remote_main or 'missing')[:8]}"
                    )

            # Stage business files only. Collaboration runtime state is outside
            # the MAIN working tree and is never staged here.
            self._run_git_command(["add", "-A"])

            db_path = self._repo_path / "database" / "center.db"
            if db_path.exists():
                self._run_git_command(["add", "--force", "database/center.db"])

            manifest_path = self._repo_path / "manifest.json"
            if manifest_path.exists():
                self._run_git_command(["add", "--force", "manifest.json"])

            status_out = self._run_git_command(["status", "--porcelain"])
            if not status_out:
                logger.info("No changes to commit")
                return True

            commit_message = f"{user}: {message}"
            self._run_git_command(["commit", "-m", commit_message])
            logger.info(f"Committed: {commit_message}")

            # Exactly one push attempt. If the remote changed, fail safely;
            # never pull/rebase or repeat the same stale push.
            self._push_only(expected_remote_commit=expected_main_commit)
            logger.info("Push-only successful")
            return True
        except RepositoryConflictError as e:
            logger.error(f"Publish-only rejected due to concurrency conflict: {e}")
            raise PushFailedError(f"Publish rejected: {e}")
        except Exception as e:
            logger.error(f"Publish-only failed: {e}")
            raise PushFailedError(f"Push failed: {e}")

    def status(self) -> Dict[str, Any]:
        status = {
            "provider": self._name,
            "connected": self._connected,
            "offline": self._offline,
            "repo_path": str(self._repo_path),
            "branch": self._branch,
            "lock_branch": self._lock_branch,
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
        if not self._connected or self._repo is None:
            return None
        try:
            self._run_git_command(["fetch", "origin", self._branch])
            result = self._run_git_command(["show", f"origin/{self._branch}:manifest.json"])
            return json.loads(result)
        except Exception:
            return None

    def current_version(self) -> int:
        manifest_path = self._repo_path / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("runtime_version", 0)
            except Exception:
                return 0
        return 0

    def update_manifest(self, version: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
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
        if not GIT_AVAILABLE or not self._connected:
            return False
        try:
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
        if not GIT_AVAILABLE or not self._repo_path.exists() or not (self._repo_path / ".git").exists():
            return False
        if self._repo:
            try:
                branches = self._run_git_command(["branch"]).split("\n")
                if self._branch not in [b.strip().replace("*", "").strip() for b in branches if b.strip()]:
                    logger.warning(f"Branch {self._branch} not found")
                    return False
            except Exception:
                return False
        return True

    def is_configured(self) -> bool:
        return bool(self._repository_url)

    def reset_to_remote(self, branch: Optional[str] = None) -> bool:
        if branch is None:
            branch = self._branch
        try:
            try:
                self._run_git_command(["rebase", "--abort"])
            except Exception:
                pass
            self._run_git_command(["fetch", "origin"])
            self._run_git_command(["reset", "--hard", f"origin/{branch}"])
            logger.info(f"Reset local repository to origin/{branch}")
            return True
        except Exception as e:
            logger.exception(f"Reset to remote failed: {e}")
            return False

    def get_remote_main_commit(self) -> Optional[str]:
        if not self._connected or self._repo is None:
            return None
        try:
            self._run_git_command(["fetch", "origin", self._branch])
            return self._run_git_command(["rev-parse", f"origin/{self._branch}"]).strip()
        except Exception as e:
            logger.warning(f"Failed to get remote MAIN commit: {e}")
            return None

    def get_local_main_commit(self) -> Optional[str]:
        if not self._connected or self._repo is None:
            return None
        try:
            return self._run_git_command(["rev-parse", "HEAD"]).strip()
        except Exception as e:
            logger.warning(f"Failed to get local MAIN commit: {e}")
            return None

    def _ensure_repo(self):
        if not self._connected:
            raise RuntimeError("Git provider not connected. Call connect() first.")
        if self._repo is None:
            raise RuntimeError("Repository not initialized. Call clone() first.")