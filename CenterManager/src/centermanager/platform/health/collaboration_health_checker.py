# -*- coding: utf-8 -*-
"""
CollaborationHealthChecker - health checks for collaboration components.
"""
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

from centermanager.platform.collaboration.lock_manager import LockManager
from centermanager.platform.collaboration.metadata_repository import MetadataRepository
from centermanager.platform.synchronization import SynchronizationProvider
from centermanager.platform.version.version_manager import VersionManager

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class HealthCheckResult:
    status: HealthStatus
    details: Dict[str, Any]
    message: str = ""


class CollaborationHealthChecker:
    def __init__(
        self,
        lock_manager: LockManager,
        metadata_repository: MetadataRepository,
        version_manager: VersionManager,
        sync_provider: Optional[SynchronizationProvider] = None,
    ):
        self._lock_manager = lock_manager
        self._metadata_repository = metadata_repository
        self._version_manager = version_manager
        self._sync_provider = sync_provider

    def check_all(self) -> HealthCheckResult:
        results = {
            "lock": self._check_lock(),
            "metadata": self._check_metadata(),
            "version": self._check_version(),
            "heartbeat": self._check_heartbeat(),
            "git": self._check_git(),
        }

        # Determine overall status
        statuses = [r["status"] for r in results.values() if r]
        if HealthStatus.CRITICAL in statuses:
            overall = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.HEALTHY

        details = results
        return HealthCheckResult(
            status=overall,
            details=details,
            message=f"Collaboration health: {overall.value}",
        )

    def _check_lock(self) -> Dict[str, Any]:
        try:
            is_locked = self._lock_manager.is_locked()
            owner = self._lock_manager.get_owner()
            is_stale = self._lock_manager.is_stale()
            status = HealthStatus.HEALTHY
            if is_locked and is_stale:
                status = HealthStatus.WARNING
            elif is_locked:
                status = HealthStatus.HEALTHY
            return {
                "status": status,
                "is_locked": is_locked,
                "owner": owner,
                "is_stale": is_stale,
            }
        except Exception as e:
            logger.exception("Lock health check failed")
            return {"status": HealthStatus.CRITICAL, "error": str(e)}

    def _check_metadata(self) -> Dict[str, Any]:
        try:
            lock = self._metadata_repository.load_lock()
            version = self._metadata_repository.load_version()
            deployment = self._metadata_repository.load_deployment()
            status = HealthStatus.HEALTHY
            missing = []
            if not lock:
                missing.append("lock.json")
            if not version:
                missing.append("version.json")
            if not deployment:
                missing.append("deployment.json")
            if missing:
                status = HealthStatus.CRITICAL
            return {
                "status": status,
                "lock_exists": bool(lock),
                "version_exists": bool(version),
                "deployment_exists": bool(deployment),
                "missing": missing,
            }
        except Exception as e:
            logger.exception("Metadata health check failed")
            return {"status": HealthStatus.CRITICAL, "error": str(e)}

    def _check_version(self) -> Dict[str, Any]:
        try:
            version = self._version_manager.get_current_version()
            return {"status": HealthStatus.HEALTHY, "version": version}
        except Exception as e:
            logger.exception("Version health check failed")
            return {"status": HealthStatus.CRITICAL, "error": str(e)}

    def _check_heartbeat(self) -> Dict[str, Any]:
        try:
            lock = self._metadata_repository.load_lock()
            if not lock.get("locked", False):
                return {"status": HealthStatus.HEALTHY, "running": False}

            last_hb = lock.get("last_heartbeat")
            if not last_hb:
                return {"status": HealthStatus.WARNING, "running": True, "last_heartbeat": None}

            from datetime import datetime
            last = datetime.fromisoformat(last_hb)
            age = (datetime.now() - last).total_seconds()
            status = HealthStatus.HEALTHY if age < 60 else HealthStatus.WARNING
            return {"status": status, "running": True, "age_seconds": age}
        except Exception as e:
            return {"status": HealthStatus.CRITICAL, "error": str(e)}

    def _check_git(self) -> Dict[str, Any]:
        if self._sync_provider is None:
            return {"status": HealthStatus.HEALTHY, "enabled": False}

        try:
            status = self._sync_provider.status()
            sync_status = status.get("status", "offline")
            if sync_status == "offline":
                return {"status": HealthStatus.WARNING, "sync_status": sync_status}
            elif sync_status == "error":
                return {"status": HealthStatus.WARNING, "sync_status": sync_status, "error": status.get("last_error")}
            return {"status": HealthStatus.HEALTHY, "sync_status": sync_status}
        except Exception as e:
            return {"status": HealthStatus.CRITICAL, "error": str(e)}