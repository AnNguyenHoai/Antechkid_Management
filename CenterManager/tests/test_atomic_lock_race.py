# -*- coding: utf-8 -*-
"""Tests for atomic lock acquisition race condition."""

import pytest
import subprocess
import json
import threading
import time
from pathlib import Path
from datetime import datetime

from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


@pytest.fixture
def seeded_remote(tmp_path):
    """Create a seeded bare remote repository."""
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, capture_output=True, check=True)

    source_path = tmp_path / "source"
    source_path.mkdir()
    subprocess.run(["git", "init"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=source_path, capture_output=True, check=True)

    (source_path / "README.md").write_text("# Test repo")
    manifest = {
        "schema_version": 1,
        "runtime_version": 1,
        "database_version": 1,
        "minimum_app_version": "0.1.0",
        "publisher": "Test",
        "branch": "main",
        "created_at": datetime.now().isoformat(),
        "published_at": None,
    }
    with open(source_path / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    subprocess.run(["git", "branch", "-M", "main"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "push", str(remote_path), "main"], cwd=source_path, capture_output=True, check=True)

    return remote_path


def test_atomic_lock_race(seeded_remote, tmp_path):
    """
    Test that two concurrent lock acquisitions result in exactly one winner.
    Uses a real bare remote and GitSynchronizationProvider.
    """
    results = []
    lock = threading.Lock()

    def acquire_worker(worker_id: str, repo_path: Path):
        try:
            # Clone repository for this worker
            worker_repo = repo_path / f"worker_{worker_id}"
            subprocess.run(["git", "clone", "--branch", "main", str(seeded_remote), str(worker_repo)], check=True)
            subprocess.run(["git", "config", "user.name", f"Test {worker_id}"], cwd=worker_repo, check=True)
            subprocess.run(["git", "config", "user.email", f"test_{worker_id}@example.com"], cwd=worker_repo, check=True)

            provider = GitSynchronizationProvider(
                repo_path=worker_repo,
                repository_url=str(seeded_remote),
                token="",
                branch="main"
            )
            provider.connect()

            lock_data = {
                "locked": True,
                "session_id": f"session_{worker_id}",
                "owner": f"User {worker_id}",
                "username": f"User {worker_id}",
                "user_id": worker_id,
                "acquired_at": datetime.now().isoformat(),
                "last_heartbeat": datetime.now().isoformat(),
                "machine": f"machine_{worker_id}",
            }

            success = provider.acquire_lock(lock_data)
            with lock:
                results.append((worker_id, success))

            if success:
                # Release after a moment
                time.sleep(0.5)
                provider.release_lock(f"User {worker_id}")
            else:
                # Check if it's waiting or failed
                pass

        except Exception as e:
            with lock:
                results.append((worker_id, f"ERROR: {e}"))

    # Run multiple rounds to increase confidence
    rounds = 20
    double_write_count = 0

    for round_num in range(rounds):
        repo_root = tmp_path / f"round_{round_num}"
        repo_root.mkdir(parents=True, exist_ok=True)

        threads = []
        for i in range(2):
            t = threading.Thread(target=acquire_worker, args=(str(i), repo_root))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        successes = [r for r in results if r[1] is True]
        if len(successes) > 1:
            double_write_count += 1

        # Reset results for next round
        results.clear()

    assert double_write_count == 0, f"Double write occurred {double_write_count} times out of {rounds} rounds"