# -*- coding: utf-8 -*-
"""Repository management for deployment."""

import logging
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import os
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.synchronization.git.git_exceptions import GitException
from centermanager.platform.deployment.deployment_config import DeploymentConfig
from centermanager.platform.deployment.git_locator import locate_git
from centermanager.core.paths import get_paths

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manage Git repository for deployment."""

    def __init__(self) -> None:
        self._config = DeploymentConfig()
        self._repo_path = self._config.get_local_path()
        self._git_executable = self._config.get_git_executable()
        # If git executable not set, try to locate
        if not self._git_executable:
            git_path = locate_git()
            if git_path:
                self._git_executable = str(git_path)
                self._config.set_git_executable(str(git_path))

    def _get_git_provider(self) -> GitProvider:
        """Create GitProvider with current configuration."""
        token = self._config.get_token()
        url = self._config.get_repository_url()
        branch = self._config.get_branch()
        creds = GitCredentials(
            repository_url=url,
            branch=branch,
            token=token,
            username="",  # not needed for cloning with token
            email="",
        )
        # Pass git executable to GitProvider
        provider = GitProvider(self._repo_path, creds)
        if self._git_executable:
            # GitProvider does not currently accept git_executable; we'll need to extend it.
            # For now, we assume system git is available.
            # TODO: extend GitProvider to accept git_executable.
            pass
        return provider

    def clone_repository(self, progress_callback: Optional[callable] = None) -> bool:
        """
        Clone repository from configured URL.
        Returns True on success, False on failure.
        progress_callback: function(step, message, percent)
        """
        try:
            url = self._config.get_repository_url()
            print("Đây là url",url)
            if not url:
                logger.error("Repository URL is not configured.")
                return False

            token = self._config.get_token()
            if not token:
                logger.error("Git token is not configured.")
                return False

            branch = self._config.get_branch()

            # Ensure parent directory exists
            self._repo_path.parent.mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback("clone", f"Cloning repository from {url}...", 10)

            # Use GitProvider's clone capability.
            # GitProvider currently does not have a standalone clone method; it expects repository to exist.
            # We'll implement a simple clone using Git commands directly.
            # We need to extend GitProvider or create a helper.
            # For now, implement a simple clone with subprocess.

            import subprocess
            git_cmd = self._git_executable or "git"
            cmd = [git_cmd, "clone", url, str(self._repo_path)]
            # Add token authentication
            if token:
                # Use token in URL for HTTPS
                if "://" in url:
                    protocol, rest = url.split("://", 1)
                    if "@" in rest:
                        rest = rest.split("@")[-1]
                    auth_url = f"{protocol}://{token}@{rest}"
                else:
                    auth_url = url
                cmd = [git_cmd, "clone", auth_url, str(self._repo_path)]
            else:
                cmd = [git_cmd, "clone", url, str(self._repo_path)]

            if branch != "main":
                cmd.extend(["--branch", branch])

            if progress_callback:
                progress_callback("clone", "Running git clone...", 30)

            env = os.environ.copy()
            if token:
                env["GIT_ASKPASS"] = "echo"
                env["GIT_USER"] = ""  # not used with token
                env["GIT_PASSWORD"] = token

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"Clone failed: {error_msg}")
                if progress_callback:
                    progress_callback("clone_failed", f"Clone failed: {error_msg}", 100)
                return False

            if progress_callback:
                progress_callback("clone", "Clone successful. Validating...", 60)

            # Validate cloned repository
            if not self.is_valid():
                if progress_callback:
                    progress_callback("clone_failed", "Repository is invalid after clone.", 100)
                return False

            if progress_callback:
                progress_callback("clone", "Repository validation passed.", 80)

            # Now, ensure runtime directories are initialized from repository
            self._sync_repository_to_runtime()

            if progress_callback:
                progress_callback("clone", "Deployment completed.", 100)

            return True

        except Exception as e:
            logger.exception("Clone failed")
            if progress_callback:
                progress_callback("clone_failed", f"Clone error: {str(e)}", 100)
            return False

    def _sync_repository_to_runtime(self) -> None:
        """Copy database and metadata from repository to runtime."""
        repo_db = self._repo_path / "database" / "center.db"
        runtime_db = get_paths().database_dir / "center.db"
        if repo_db.exists():
            runtime_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_db, runtime_db)
            logger.info(f"Copied database from repository to runtime: {runtime_db}")

        repo_meta = self._repo_path / "metadata"
        runtime_meta = get_paths().metadata_dir
        if repo_meta.exists():
            runtime_meta.mkdir(parents=True, exist_ok=True)
            for f in repo_meta.glob("*.json"):
                shutil.copy2(f, runtime_meta / f.name)
            logger.info(f"Copied metadata from repository to runtime: {runtime_meta}")

        # Also copy reports if any
        repo_reports = self._repo_path / "reports"
        runtime_reports = get_paths().reports_dir
        if repo_reports.exists():
            shutil.copytree(repo_reports, runtime_reports, dirs_exist_ok=True)
            logger.info(f"Copied reports from repository to runtime: {runtime_reports}")

    def is_valid(self) -> bool:
        """Check if repository is valid (contains required structure)."""
        if not self._repo_path.exists():
            return False
        git_dir = self._repo_path / ".git"
        if not git_dir.exists():
            return False
        # Check for at least database/center.db and metadata/*.json
        db_path = self._repo_path / "database" / "center.db"
        if not db_path.exists():
            logger.warning("Repository missing database/center.db")
            return False
        meta_dir = self._repo_path / "metadata"
        if not meta_dir.exists():
            logger.warning("Repository missing metadata directory")
            return False
        # At least lock.json and version.json should exist
        required_meta = ["lock.json", "version.json", "deployment.json"]
        for fname in required_meta:
            if not (meta_dir / fname).exists():
                logger.warning(f"Repository missing metadata/{fname}")
                return False
        return True

    def open_repository(self) -> Optional[GitProvider]:
        """Return GitProvider for the repository, or None if invalid."""
        if not self.is_valid():
            return None
        return self._get_git_provider()

    def get_repository_path(self) -> Path:
        return self._repo_path

    def is_deployed(self) -> bool:
        """Check if deployment is already set up."""
        # Check if repository exists and is valid, and runtime has database/metadata
        if not self.is_valid():
            return False
        # Check runtime database exists
        runtime_db = get_paths().database_dir / "center.db"
        if not runtime_db.exists():
            return False
        return True