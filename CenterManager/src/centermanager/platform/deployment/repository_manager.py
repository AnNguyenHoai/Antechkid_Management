# -*- coding: utf-8 -*-
"""Repository management for deployment."""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from centermanager.core.git_locator import locate_git
from centermanager.core.git_url_safety import validate_repository_url
from centermanager.core.paths import get_paths
from centermanager.platform.deployment.deployment_config import DeploymentConfig
from centermanager.platform.synchronization._windows_subprocess import hidden_subprocess_kwargs
from centermanager.platform.synchronization.git.git_credential_helper import GitCredentialHelper
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git_windows_auth import append_http_auth_config

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manage Git repository for deployment."""

    def __init__(self) -> None:
        self._config = DeploymentConfig()
        self._repo_path = self._config.get_local_path()
        self._git_executable = self._config.get_git_executable()
        if not self._git_executable:
            git_path = locate_git()
            if git_path:
                self._git_executable = str(git_path)
                self._config.set_git_executable(str(git_path))

    def _get_git_provider(self) -> GitProvider:
        """Create GitProvider with current configuration."""
        token = self._config.get_token()
        url = validate_repository_url(self._config.get_repository_url())
        branch = self._config.get_branch()
        creds = GitCredentials(
            repository_url=url,
            branch=branch,
            token=token,
            username="",
            email="",
        )
        return GitProvider(self._repo_path, creds, git_executable=self._git_executable)

    def clone_repository(self, progress_callback: Optional[callable] = None) -> bool:
        """Clone the configured repository without putting credentials in URL/argv."""
        helper: Optional[GitCredentialHelper] = None
        try:
            raw_url = self._config.get_repository_url()
            if not raw_url:
                logger.error("Repository URL is not configured.")
                return False
            url = validate_repository_url(raw_url)

            token = self._config.get_token()
            if not token:
                logger.error("Git service credential is not configured.")
                return False

            branch = self._config.get_branch()
            self._repo_path.parent.mkdir(parents=True, exist_ok=True)

            if progress_callback:
                progress_callback("clone", f"Cloning repository from {url}...", 10)

            if not self._git_executable:
                logger.error("Git executable is unavailable; deployment clone cannot start.")
                if progress_callback:
                    progress_callback("clone_failed", "Git executable is unavailable on this machine.", 100)
                return False

            # The remote URL is always credential-free. Authentication is
            # process-local: askpass on non-Windows and GIT_CONFIG extraHeader on
            # Windows GUI builds. The service credential never enters argv or
            # persisted .git/config.
            cmd = [self._git_executable, "clone"]
            if branch != "main":
                cmd.extend(["--branch", branch])
            cmd.extend([url, str(self._repo_path)])

            if progress_callback:
                progress_callback("clone", "Running git clone...", 30)

            helper = GitCredentialHelper("git", token)
            env = os.environ.copy()
            env.update(helper.setup_environment())
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_CONFIG_COUNT"] = "1"
            env["GIT_CONFIG_KEY_0"] = "credential.helper"
            env["GIT_CONFIG_VALUE_0"] = ""
            if sys.platform == "win32":
                env["GIT_CONFIG_COUNT"] = "2"
                env["GIT_CONFIG_KEY_1"] = "core.askpass"
                env["GIT_CONFIG_VALUE_1"] = ""
                append_http_auth_config(env, url, helper.http_auth_header())

            run_kwargs = {
                "capture_output": True,
                "text": True,
                "env": env,
                "check": False,
            }
            run_kwargs.update(hidden_subprocess_kwargs())
            result = subprocess.run(cmd, **run_kwargs)
            if result.returncode != 0:
                # Do not surface raw command arguments or environment. Git's
                # HTTPS errors do not contain the process-local credential.
                error_msg = (result.stderr or "").strip()
                logger.error("Clone failed: %s", error_msg)
                if progress_callback:
                    progress_callback("clone_failed", f"Clone failed: {error_msg}", 100)
                return False

            if progress_callback:
                progress_callback("clone", "Clone successful. Validating...", 60)

            if not self.is_valid():
                if progress_callback:
                    progress_callback("clone_failed", "Repository is invalid after clone.", 100)
                return False

            if progress_callback:
                progress_callback("clone", "Repository validation passed.", 80)

            self._sync_repository_to_runtime()

            if progress_callback:
                progress_callback("clone", "Deployment completed.", 100)
            return True

        except ValueError as exc:
            logger.error("Repository URL rejected by transport policy: %s", exc)
            if progress_callback:
                progress_callback("clone_failed", "Repository URL must use credential-free HTTPS.", 100)
            return False
        except Exception:
            logger.exception("Clone failed")
            if progress_callback:
                progress_callback("clone_failed", "Clone error. Check logs for non-secret diagnostics.", 100)
            return False
        finally:
            if helper is not None:
                helper.cleanup()

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
        db_path = self._repo_path / "database" / "center.db"
        if not db_path.exists():
            logger.warning("Repository missing database/center.db")
            return False
        meta_dir = self._repo_path / "metadata"
        if not meta_dir.exists():
            logger.warning("Repository missing metadata directory")
            return False
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
        if not self.is_valid():
            return False
        runtime_db = get_paths().database_dir / "center.db"
        if not runtime_db.exists():
            return False
        return True
