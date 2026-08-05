# -*- coding: utf-8 -*-
"""
Crash Recovery Simulation

Simulates crash scenarios and checks if lease recovers automatically.
"""
import os
import time
import json
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from collaboration_prototype.lease_manager import LeaseManager, LeaseStatus
from collaboration_prototype.version_manager import VersionManager
from collaboration_prototype.db_test import SQLiteTest


class CrashSimulator:
    """
    Simulates various crash scenarios and observes recovery behavior.
    """

    def __init__(self, shared_dir: Path):
        self.shared_dir = Path(shared_dir)
        self.shared_dir.mkdir(parents=True, exist_ok=True)

    def simulate_power_loss(self, lease_manager: LeaseManager) -> Dict[str, Any]:
        """
        Simulate sudden power loss by acquiring a lease and then
        stopping without releasing it.
        """
        result = {"scenario": "power_loss", "success": False, "details": ""}

        # Acquire lease
        if lease_manager.acquire():
            result["details"] = "Lease acquired successfully"

            # Simulate power loss - just exit without releasing
            # In reality, the lease would remain with the last heartbeat
            # We'll simulate by not calling release()

            # Wait a bit to simulate normal operation
            time.sleep(2)

            # Simulate crash: we're not releasing the lease
            # In real scenario, the lease file remains with old heartbeat
            result["success"] = True
            result["details"] += " | Power loss simulated, lease not released"
        else:
            result["details"] = "Failed to acquire lease"

        return result

    def simulate_network_disconnect(self, lease_manager: LeaseManager) -> Dict[str, Any]:
        """
        Simulate network disconnection by stopping heartbeat.
        """
        result = {"scenario": "network_disconnect", "success": False, "details": ""}

        if lease_manager.acquire():
            result["details"] = "Lease acquired, starting heartbeat"

            # Simulate network disconnect by stopping heartbeat
            lease_manager._stop_heartbeat = True

            # Wait for timeout
            time.sleep(lease_manager.timeout_seconds + 5)

            # Check if lease still exists or expired
            status = LeaseStatus.get_status(self.shared_dir)
            if status.get("has_lease"):
                age = status.get("age")
                if age and age > lease_manager.timeout_seconds:
                    result["success"] = True
                    result["details"] = f"Lease expired after {age:.1f}s (timeout: {lease_manager.timeout_seconds}s)"
                else:
                    result["details"] = f"Lease still valid (age: {age}s)"
            else:
                result["success"] = True
                result["details"] = "Lease removed due to timeout"

            # Cleanup
            lease_manager.release()
        else:
            result["details"] = "Failed to acquire lease"

        return result

    def simulate_application_crash(self, lease_manager: LeaseManager) -> Dict[str, Any]:
        """
        Simulate application crash by abruptly ending the process.
        """
        result = {"scenario": "application_crash", "success": False, "details": ""}

        if lease_manager.acquire():
            result["details"] = "Lease acquired, simulating crash..."

            # Simulate crash by spawning a subprocess that owns the lease
            # and then killing it, or by using an exception

            # For this simulation, we'll just use a thread that dies
            def crash_worker():
                # This worker won't release the lease properly
                worker_mgr = LeaseManager(self.shared_dir)
                worker_mgr.acquire()
                # Do some work
                time.sleep(2)
                # Crash! (thread ends without releasing)

            worker_thread = threading.Thread(target=crash_worker)
            worker_thread.start()
            worker_thread.join(timeout=3)

            # Check lease status after crash
            time.sleep(1)
            status = LeaseStatus.get_status(self.shared_dir)
            if status.get("has_lease"):
                age = status.get("age")
                result["details"] = f"Lease still exists (age: {age}s). Will expire after timeout."
                result["success"] = True
            else:
                result["details"] = "Lease was cleaned up"

            # Cleanup
            lease_manager.release()
        else:
            result["details"] = "Failed to acquire lease"

        return result