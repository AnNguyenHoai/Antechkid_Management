# -*- coding: utf-8 -*-
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from .synchronization_provider import SynchronizationProvider
from .git.git_provider import GitProvider
from .git.git_credentials import GitCredentials
from .git.git_status import GitStatus
from .git.git_exceptions import GitException
from centermanager.core.paths import get_paths

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

    def _sync_data_files(self) -> None:
        """
        Copy database, metadata, and reports into the repository
        so that Git can track changes.
        """
        paths = get_paths()
        # Ensure repo directories exist
        (self._repo_path / "database").mkdir(parents=True, exist_ok=True)
        (self._repo_path / "metadata").mkdir(parents=True, exist_ok=True)
        (self._repo_path / "reports").mkdir(parents=True, exist_ok=True)

        # Copy database
        db_src = paths.database_dir / "center.db"
        db_dst = self._repo_path / "database" / "center.db"
        if db_src.exists():
            shutil.copy2(db_src, db_dst)
            logger.debug(f"Copied database: {db_src} -> {db_dst}")
        else:
            logger.warning(f"Database file not found: {db_src}")

        # Copy metadata
        meta_src = paths.metadata_dir
        if meta_src.exists():
            for f in meta_src.glob("*.json"):
                dst = self._repo_path / "metadata" / f.name
                shutil.copy2(f, dst)
                logger.debug(f"Copied metadata: {f} -> {dst}")
        else:
            logger.warning(f"Metadata directory not found: {meta_src}")

        # Copy reports (optional) - chỉ copy file mới nhất hoặc toàn bộ
        reports_src = paths.reports_dir
        if reports_src.exists():
            # Có thể copy toàn bộ cây thư mục reports nếu cần
            # Để đơn giản, hiện tại chỉ copy báo cáo của học sinh
            for student_dir in reports_src.glob("Student/*"):
                if student_dir.is_dir():
                    dst = self._repo_path / "reports" / "Student" / student_dir.name
                    dst.mkdir(parents=True, exist_ok=True)
                    for pdf in student_dir.glob("*.pdf"):
                        shutil.copy2(pdf, dst / pdf.name)
                        logger.debug(f"Copied report: {pdf} -> {dst / pdf.name}")
        else:
            logger.debug(f"Reports directory not found: {reports_src}")

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

            # Step 1: Sync data files into repository
            self._sync_data_files()

            # Step 2: Commit
            self._git_provider.commit(message, user)

            # Step 3: Push
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