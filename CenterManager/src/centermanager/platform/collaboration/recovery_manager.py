# -*- coding: utf-8 -*-
"""
RecoveryManager - inspects and recovers collaboration state after startup.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from centermanager.platform.collaboration.lock_manager import LockManager
from centermanager.platform.collaboration.metadata_repository import MetadataRepository
from centermanager.events.event_bus import EventBus
from centermanager.events.collaboration_events import (
    RecoveryStarted,
    RecoveryCompleted,
    RecoveryFailed,
)

logger = logging.getLogger(__name__)


class RecoveryManager:
    def __init__(
        self,
        lock_manager: LockManager,
        metadata_repository: MetadataRepository,
        event_bus: EventBus,
    ):
        self._lock_manager = lock_manager
        self._metadata_repository = metadata_repository
        self._event_bus = event_bus
        self._recovered = False

    def inspect_and_recover(self) -> Dict[str, Any]:
        """
        Run recovery inspection on startup.
        Returns recovery report.
        """
        report = {
            "recovered": False,
            "actions": [],
            "lock_recovered": False,
            "metadata_recovered": False,
            "version_recovered": False,
        }

        logger.info("RecoveryManager: starting inspection")

        self._event_bus.publish(RecoveryStarted())

        # 1. Check stale lock
        if self._lock_manager.is_stale():
            logger.warning("Stale lock detected during recovery")
            if self._lock_manager.recover_stale():
                report["lock_recovered"] = True
                report["actions"].append("Released stale lock")
                logger.info("Stale lock recovered")
            else:
                report["actions"].append("Stale lock recovery failed")
                logger.error("Stale lock recovery failed")

        # 2. Check metadata consistency
        metadata_ok = self._check_metadata()
        if not metadata_ok:
            report["metadata_recovered"] = self._repair_metadata()
            if report["metadata_recovered"]:
                report["actions"].append("Repaired metadata")
            else:
                report["actions"].append("Metadata repair failed")

        # 3. Check version consistency
        version_ok = self._check_version()
        if not version_ok:
            report["version_recovered"] = self._repair_version()
            if report["version_recovered"]:
                report["actions"].append("Repaired version")
            else:
                report["actions"].append("Version repair failed")

        report["recovered"] = (
            report["lock_recovered"] or
            report["metadata_recovered"] or
            report["version_recovered"]
        )

        if report["recovered"]:
            self._event_bus.publish(RecoveryCompleted())
        else:
            self._event_bus.publish(RecoveryFailed())

        logger.info(f"Recovery inspection complete: {report}")
        return report

    def _check_metadata(self) -> bool:
        """Check if metadata files exist and are valid."""
        try:
            lock = self._metadata_repository.load_lock()
            version = self._metadata_repository.load_version()
            deployment = self._metadata_repository.load_deployment()
            return bool(lock and version and deployment)
        except Exception as e:
            logger.exception("Metadata check failed")
            return False

    def _repair_metadata(self) -> bool:
        """Attempt to repair missing/invalid metadata."""
        try:
            # Ensure lock exists
            lock = self._metadata_repository.load_lock()
            if not lock:
                self._metadata_repository.save_lock({
                    "locked": False,
                    "owner": None,
                    "session_id": None,
                    "started_at": None,
                    "last_heartbeat": None,
                })
                logger.info("Lock metadata repaired")

            # Ensure version exists
            version = self._metadata_repository.load_version()
            if not version:
                self._metadata_repository.save_version({"platform_version": 1})
                logger.info("Version metadata repaired")

            # Ensure deployment exists
            deployment = self._metadata_repository.load_deployment()
            if not deployment:
                self._metadata_repository.save_deployment({"profile": "Standalone"})
                logger.info("Deployment metadata repaired")

            return True
        except Exception as e:
            logger.exception("Metadata repair failed")
            return False

    def _check_version(self) -> bool:
        """Check if platform_version is valid."""
        try:
            version_data = self._metadata_repository.load_version()
            if not version_data or "platform_version" not in version_data:
                return False
            return True
        except Exception:
            return False

    def _repair_version(self) -> bool:
        """Repair version metadata."""
        try:
            self._metadata_repository.save_version({"platform_version": 1})
            return True
        except Exception as e:
            logger.exception("Version repair failed")
            return False

    @property
    def recovered(self) -> bool:
        return self._recovered