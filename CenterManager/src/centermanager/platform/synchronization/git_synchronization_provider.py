# -*- coding: utf-8 -*-
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .synchronization_provider import SynchronizationProvider
from .git.git_provider import GitProvider
from .git.git_credentials import GitCredentials
from .git.git_status import GitStatus
from .git.git_exceptions import GitException

logger = logging.getLogger(__name__)


class GitSynchronizationProvider(SynchronizationProvider):
    def __init__(
        self,
        repo_path: Path,
        credentials: Optional[GitCredentials] = None,
    ):
        self._repo_path = repo_path
        self._credentials = credentials
        self._git_provider = GitProvider(repo_path, credentials)
        self._status = GitStatus.OFFLINE
        self._last_error = None

        # Initialize repository if needed
        if self._credentials:
            self._git_provider.init_repository()

    def fetch(self) -> bool:
        if not self._credentials:
            return False
        try:
            self._git_provider.fetch()
            self._status = GitStatus.CONNECTED
            return True
        except GitException as e:
            self._last_error = str(e)
            self._status = GitStatus.ERROR
            logger.error(f"Git fetch failed: {e}")
            return False

    def pull(self) -> bool:
        if not self._credentials:
            return False
        try:
            self._git_provider.pull()
            self._status = GitStatus.CONNECTED
            return True
        except GitException as e:
            self._last_error = str(e)
            self._status = GitStatus.ERROR
            logger.error(f"Git pull failed: {e}")
            return False

    def publish(self, message: str, user: str) -> bool:
        if not self._credentials:
            return False
        try:
            self._status = GitStatus.PUBLISHING
            # Commit
            self._git_provider.commit(message, user)
            # Push
            self._git_provider.push()
            self._status = GitStatus.CONNECTED
            return True
        except GitException as e:
            self._last_error = str(e)
            self._status = GitStatus.ERROR
            logger.error(f"Git publish failed: {e}")
            return False

    def status(self) -> Dict[str, Any]:
        base_status = self._git_provider.status()
        return {
            **base_status,
            "last_error": self._last_error,
            "has_credentials": self._credentials is not None,
        }

    def validate(self) -> bool:
        if not self._credentials:
            return False
        try:
            self.fetch()
            return True
        except Exception:
            return False