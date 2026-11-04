# -*- coding: utf-8 -*-
"""
Lease Manager Prototype

Simulates acquiring, renewing, and releasing a lease file
in a shared Google Drive folder.
"""
import os
import json
import time
import uuid
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class LeaseManager:
    """
    Manages a lease file (.lease) in a shared directory.
    Implements:
    - Acquire lease with heartbeat
    - Renew lease periodically
    - Release lease
    - Check if lease is active
    """

    DEFAULT_LEASE_TIMEOUT = 30  # seconds
    DEFAULT_HEARTBEAT_INTERVAL = 10  # seconds

    def __init__(
        self,
        shared_dir: Path,
        lease_filename: str = "write.lease",
        timeout_seconds: int = DEFAULT_LEASE_TIMEOUT,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
    ):
        self.shared_dir = Path(shared_dir)
        self.lease_file = self.shared_dir / lease_filename
        self.timeout_seconds = timeout_seconds
        self.heartbeat_interval = heartbeat_interval
        self._owner_id = str(uuid.uuid4())
        self._has_lease = False
        self._heartbeat_thread = None
        self._stop_heartbeat = False

    def acquire(self) -> bool:
        """
        Attempt to acquire the lease.
        Returns True if successful, False otherwise.
        """
        try:
            # Ensure shared directory exists
            self.shared_dir.mkdir(parents=True, exist_ok=True)

            # Check if lease file exists and is still valid
            if self.lease_file.exists():
                lease_data = self._read_lease()
                if lease_data:
                    last_heartbeat = datetime.fromisoformat(lease_data.get("last_heartbeat", ""))
                    elapsed = (datetime.now() - last_heartbeat).total_seconds()
                    if elapsed < self.timeout_seconds:
                        # Lease is still valid, cannot acquire
                        return False

            # Create or overwrite lease file
            lease_data = {
                "owner_id": self._owner_id,
                "acquired_at": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
                "timeout_seconds": self.timeout_seconds,
            }
            self._write_lease(lease_data)
            self._has_lease = True

            # Start heartbeat thread
            self._start_heartbeat()

            return True

        except Exception as e:
            print(f"[LeaseManager] Acquire failed: {e}")
            return False

    def release(self) -> bool:
        """
        Release the lease.
        """
        self._stop_heartbeat = True
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2)

        self._has_lease = False
        try:
            if self.lease_file.exists():
                self.lease_file.unlink()
            return True
        except Exception as e:
            print(f"[LeaseManager] Release failed: {e}")
            return False

    def is_owner(self) -> bool:
        """
        Check if this instance currently owns the lease.
        """
        if not self._has_lease:
            return False

        try:
            if not self.lease_file.exists():
                return False
            lease_data = self._read_lease()
            if not lease_data:
                return False
            return lease_data.get("owner_id") == self._owner_id
        except Exception:
            return False

    def get_current_owner(self) -> Optional[str]:
        """
        Get the owner ID of the current lease, if any.
        """
        try:
            if not self.lease_file.exists():
                return None
            lease_data = self._read_lease()
            if not lease_data:
                return None
            last_heartbeat = datetime.fromisoformat(lease_data.get("last_heartbeat", ""))
            elapsed = (datetime.now() - last_heartbeat).total_seconds()
            if elapsed >= self.timeout_seconds:
                # Lease has expired
                return None
            return lease_data.get("owner_id")
        except Exception:
            return None

    def get_lease_age(self) -> Optional[float]:
        """
        Get the age of the current lease in seconds.
        """
        try:
            if not self.lease_file.exists():
                return None
            lease_data = self._read_lease()
            if not lease_data:
                return None
            last_heartbeat = datetime.fromisoformat(lease_data.get("last_heartbeat", ""))
            return (datetime.now() - last_heartbeat).total_seconds()
        except Exception:
            return None

    def _read_lease(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self.lease_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_lease(self, data: Dict[str, Any]) -> None:
        with open(self.lease_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _start_heartbeat(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        self._stop_heartbeat = False
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop_heartbeat and self._has_lease:
            try:
                if self.lease_file.exists():
                    lease_data = self._read_lease()
                    if lease_data and lease_data.get("owner_id") == self._owner_id:
                        lease_data["last_heartbeat"] = datetime.now().isoformat()
                        self._write_lease(lease_data)
            except Exception as e:
                print(f"[LeaseManager] Heartbeat error: {e}")

            time.sleep(self.heartbeat_interval)


class LeaseStatus:
    """Helper to check lease status without owning it."""
    @staticmethod
    def get_status(shared_dir: Path, lease_filename: str = "write.lease") -> Dict[str, Any]:
        lease_file = Path(shared_dir) / lease_filename
        if not lease_file.exists():
            return {"has_lease": False, "owner_id": None, "age": None}

        try:
            with open(lease_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_heartbeat = datetime.fromisoformat(data.get("last_heartbeat", ""))
            age = (datetime.now() - last_heartbeat).total_seconds()
            return {
                "has_lease": True,
                "owner_id": data.get("owner_id"),
                "age": age,
                "last_heartbeat": last_heartbeat.isoformat(),
            }
        except Exception as e:
            return {"has_lease": True, "owner_id": "unknown", "age": None, "error": str(e)}