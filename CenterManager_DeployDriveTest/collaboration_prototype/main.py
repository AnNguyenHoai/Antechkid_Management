#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collaboration Architecture Prototype - Main Entry Point

Runs all experiments and generates a report.
"""
import os
import sys
import time
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from lease_manager import LeaseManager, LeaseStatus
from version_manager import VersionManager
from db_test import SQLiteTest
from sync_measure import SyncMeasurement
from crash_sim import CrashSimulator


def run_all_experiments(shared_dir: Path) -> Dict[str, Any]:
    """Run all experiments and return results."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "shared_directory": str(shared_dir),
        "experiments": {},
    }

    print("=" * 60)
    print("Collaboration Architecture Prototype")
    print(f"Shared Directory: {shared_dir}")
    print("=" * 60)

    # ============================================================
    # Experiment 1: Lease Management
    # ============================================================
    print("\n[1] Lease Management Test")
    lease_mgr = LeaseManager(shared_dir)
    if lease_mgr.acquire():
        print("✓ Lease acquired successfully")
        status = LeaseStatus.get_status(shared_dir)
        print(f"  Owner: {status.get('owner_id')}")
        print(f"  Lease age: {status.get('age'):.2f}s" if status.get('age') else "  Lease age: N/A")

        lease_mgr.release()
        print("✓ Lease released")
        status = LeaseStatus.get_status(shared_dir)
        print(f"  After release: {'No lease' if not status.get('has_lease') else 'Lease still exists'}")
    else:
        print("✗ Failed to acquire lease")

    results["experiments"]["lease_management"] = {"success": lease_mgr.acquire()}

    # ============================================================
    # Experiment 2: Version Management
    # ============================================================
    print("\n[2] Version Management Test")
    version_mgr = VersionManager(shared_dir)
    old_version = version_mgr.get_current_version()
    print(f"  Initial version: {old_version}")

    new_version = version_mgr.increment_version({"test": "version_test"})
    print(f"  Incremented to: {new_version}")

    # Simulate another machine reading
    version_mgr2 = VersionManager(shared_dir)
    version_mgr2.refresh()
    print(f"  Other machine sees version: {version_mgr2.get_current_version()}")

    results["experiments"]["version_management"] = {
        "initial": old_version,
        "incremented": new_version,
        "other_detected": version_mgr2.get_current_version(),
    }

    # ============================================================
    # Experiment 3: SQLite Behavior
    # ============================================================
    print("\n[3] SQLite Behavior Test")
    db_path = shared_dir / "test.db"
    db_test = SQLiteTest(db_path, journal_mode="WAL")

    # Read initial value
    value = db_test.read_value()
    print(f"  Initial value: {value}")

    # Write new value
    db_test.write_value(f"test_{int(time.time())}")
    new_value = db_test.read_value()
    print(f"  Updated value: {new_value}")

    # Concurrent writes test
    print("  Simulating concurrent writes...")
    concurrency_results = db_test.simulate_concurrent_writes(num_writers=3, writes_per_writer=3)
    print(f"  Concurrent writes: {concurrency_results['success']} success, {concurrency_results['failures']} failures")

    # Replacement test
    print("  Testing database replacement...")
    replace_results = db_test.test_replacement()
    print(f"  Replacement atomic: {replace_results.get('atomic', False)}")
    print(f"  Verified: {replace_results.get('verified', False)}")

    results["experiments"]["sqlite"] = {
        "read_value": value,
        "concurrent_writes": concurrency_results,
        "replacement": replace_results,
    }

    # ============================================================
    # Experiment 4: Sync Latency Measurement
    # ============================================================
    print("\n[4] Sync Latency Measurement")
    sync_measure = SyncMeasurement(shared_dir)
    latency = sync_measure.measure_local_latency(num_samples=5)
    print(f"  Latency (local simulation):")
    print(f"    Min: {latency.get('min_latency', 0):.4f}s")
    print(f"    Max: {latency.get('max_latency', 0):.4f}s")
    print(f"    Avg: {latency.get('avg_latency', 0):.4f}s")

    results["experiments"]["sync_latency"] = latency

    # ============================================================
    # Experiment 5: Version Detection Latency
    # ============================================================
    print("\n[5] Version Detection Latency")
    detection = sync_measure.measure_version_detection_latency(version_mgr, poll_interval=0.5, max_wait=5.0)
    print(f"  Detection: {'✓' if detection.get('detected') else '✗'}")
    print(f"  Detection time: {detection.get('detection_time', 0):.2f}s")
    print(f"  Old version: {detection.get('old_version')} -> New: {detection.get('new_version')}")

    results["experiments"]["version_detection"] = detection

    # ============================================================
    # Experiment 6: Crash Simulation
    # ============================================================
    print("\n[6] Crash Simulation")
    crash_sim = CrashSimulator(shared_dir)

    # Power loss
    print("  Simulating power loss...")
    power_result = crash_sim.simulate_power_loss(LeaseManager(shared_dir))
    print(f"    {power_result.get('details', '')}")

    # Network disconnect
    print("  Simulating network disconnect...")
    network_result = crash_sim.simulate_network_disconnect(LeaseManager(shared_dir))
    print(f"    {network_result.get('details', '')}")

    # Application crash
    print("  Simulating application crash...")
    crash_result = crash_sim.simulate_application_crash(LeaseManager(shared_dir))
    print(f"    {crash_result.get('details', '')}")

    results["experiments"]["crash_simulation"] = {
        "power_loss": power_result,
        "network_disconnect": network_result,
        "application_crash": crash_result,
    }

    # ============================================================
    # Save Results
    # ============================================================
    results_file = shared_dir / "experiment_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"Results saved to: {results_file}")
    print("=" * 60)

    return results


def main():
    # Use a temporary directory for testing
    # In real testing, this should be a Google Drive sync folder
    with tempfile.TemporaryDirectory(prefix="collab_test_") as tmpdir:
        shared_dir = Path(tmpdir)
        print(f"Using temporary directory: {shared_dir}")

        # Run experiments
        results = run_all_experiments(shared_dir)

        # Print summary
        print("\n[Summary]")
        print(f"  Lease Management: {'✓' if results['experiments']['lease_management'].get('success') else '✗'}")
        print(f"  Version Management: {results['experiments']['version_management'].get('incremented', 'N/A')}")
        print(f"  SQLite Concurrent Writes: {results['experiments']['sqlite']['concurrent_writes']['success']} success")
        print(f"  Sync Latency (avg): {results['experiments']['sync_latency'].get('avg_latency', 0):.4f}s")
        print(f"  Version Detection: {'✓' if results['experiments']['version_detection'].get('detected') else '✗'}")


if __name__ == "__main__":
    main()