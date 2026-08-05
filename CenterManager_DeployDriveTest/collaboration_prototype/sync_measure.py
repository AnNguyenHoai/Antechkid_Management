# -*- coding: utf-8 -*-
"""
Synchronization Measurement

Measures latency of file synchronization across the shared folder.
"""
import os
import time
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class SyncMeasurement:
    """
    Measures file synchronization latency by:
    1. Creating a file with a timestamp
    2. Waiting for the file to appear on another machine
    3. Measuring the time difference

    For single-machine testing, simulates by writing a file and
    reading it back after a delay.
    """

    def __init__(self, shared_dir: Path):
        self.shared_dir = Path(shared_dir)
        self.shared_dir.mkdir(parents=True, exist_ok=True)

    def measure_local_latency(self, num_samples: int = 10) -> Dict[str, Any]:
        """
        Simulates latency measurement by writing a file and reading it back.
        This is a simulation of what would happen across machines.
        """
        latencies = []

        for i in range(num_samples):
            filename = f"sync_test_{i}_{int(time.time())}.tmp"
            filepath = self.shared_dir / filename

            # Write file
            write_time = time.perf_counter()
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json.dumps({"timestamp": datetime.now().isoformat(), "sequence": i}))

            # Simulate network delay (in real test, this is waiting for sync)
            time.sleep(0.2)

            # Read file
            read_time = time.perf_counter()
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                latency = read_time - write_time
                latencies.append(latency)

            # Cleanup
            filepath.unlink(missing_ok=True)

        if latencies:
            return {
                "min_latency": min(latencies),
                "max_latency": max(latencies),
                "avg_latency": sum(latencies) / len(latencies),
                "samples": len(latencies),
            }
        return {"error": "No samples collected"}

    def measure_version_detection_latency(
        self, version_mgr, poll_interval: float = 0.5, max_wait: float = 10.0
    ) -> Dict[str, Any]:
        """
        Measures the time it takes to detect a version change.
        Simulates by incrementing version and polling for detection.
        """
        # Increment version
        old_version = version_mgr.get_current_version()
        start_time = time.perf_counter()
        version_mgr.increment_version({"test": "measure"})

        # Poll for version change
        detected = False
        elapsed = 0
        while elapsed < max_wait:
            if version_mgr.refresh():
                new_version = version_mgr.get_current_version()
                if new_version != old_version:
                    detected = True
                    break
            time.sleep(poll_interval)
            elapsed = time.perf_counter() - start_time

        return {
            "detected": detected,
            "detection_time": elapsed if detected else None,
            "poll_interval": poll_interval,
            "max_wait": max_wait,
            "old_version": old_version,
            "new_version": version_mgr.get_current_version() if detected else None,
        }