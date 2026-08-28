# -*- coding: utf-8 -*-
"""Tests for MAIN isolation during lock acquisition and release."""

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


def get_main_head(repo_path: Path) -> str:
    """Return the current MAIN HEAD SHA."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def get_main_branch(repo_path: Path) -> str:
    """Return the current MAIN branch name."""
    return subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def get_main_status(repo_path: Path) -> str:
    """Return git status --porcelain for MAIN."""
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def remote_lock_exists(remote_path: Path) -> bool:
    """Check if lock-main exists remotely."""
    result = subprocess.run(
        ["git", "ls-remote", str(remote_path), "refs/heads/lock-main"],
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())


class TestLockIsolation:
    """Test suite verifying MAIN isolation during lock operations."""

    @pytest.fixture(autouse=True)
    def setup_repo(self, seeded_remote, tmp_path):
        """Clone the seeded remote into a local repo for each test."""
        self.repo_path = tmp_path / "repo"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(seeded_remote), str(self.repo_path)],
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo_path,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_path,
            check=True
        )
        self.remote_path = seeded_remote
        self.provider = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(seeded_remote),
            token="",
            branch="main"
        )
        self.provider.connect()
        yield
        # Cleanup: delete lock branch if left behind
        if remote_lock_exists(self.remote_path):
            subprocess.run(
                ["git", "push", str(self.remote_path), "--delete", "lock-main", "--force"],
                capture_output=True
            )

    # ---- Test A: MAIN HEAD Preservation ----
    def test_acquire_keeps_main_head_unchanged(self):
        before_head = get_main_head(self.repo_path)

        lock_data = {
            "locked": True,
            "session_id": "sess_123",
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success = self.provider.acquire_lock(lock_data)
        assert success is True

        after_head = get_main_head(self.repo_path)
        assert after_head == before_head, "MAIN HEAD changed after acquire"

        self.provider.release_lock("test_user")

    # ---- Test B: Working Tree Preservation ----
    def test_acquire_keeps_main_working_tree_clean(self):
        before_status = get_main_status(self.repo_path)
        # Ensure it's clean (untracked files from test fixture might be ignored)
        # We explicitly ignore the .git directory and any pre-existing untracked files.
        # In a fresh clone, it should be clean.
        assert before_status == "", "Initial working tree should be clean"

        lock_data = {
            "locked": True,
            "session_id": "sess_123",
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success = self.provider.acquire_lock(lock_data)
        assert success is True

        after_status = get_main_status(self.repo_path)
        assert after_status == before_status, "MAIN working tree became dirty after acquire"

        self.provider.release_lock("test_user")

    # ---- Test C: Branch Preservation ----
    def test_acquire_keeps_main_branch_unchanged(self):
        before_branch = get_main_branch(self.repo_path)
        assert before_branch == "main", "Initial branch should be main"

        lock_data = {
            "locked": True,
            "session_id": "sess_123",
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success = self.provider.acquire_lock(lock_data)
        assert success is True

        after_branch = get_main_branch(self.repo_path)
        assert after_branch == before_branch, "MAIN branch changed after acquire"

        self.provider.release_lock("test_user")

    # ---- Test D: Remote Lock Creation ----
    def test_remote_lock_created_and_verified(self):
        assert remote_lock_exists(self.remote_path) is False, "lock-main should not exist initially"

        session_id = "sess_456"
        lock_data = {
            "locked": True,
            "session_id": session_id,
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success = self.provider.acquire_lock(lock_data)
        assert success is True

        assert remote_lock_exists(self.remote_path) is True, "lock-main should exist after acquire"

        # Verify ownership
        status = self.provider.remote_lock_status()
        assert status["locked"] is True
        assert status["session_id"] == session_id
        assert status["owner"] == "test_user"

        self.provider.release_lock("test_user")

    # ---- Test E: Ownership Verification ----
    def test_acquisition_fails_if_lock_held_by_other(self):
        # First acquire by user A
        lock_data_a = {
            "locked": True,
            "session_id": "sess_A",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success_a = self.provider.acquire_lock(lock_data_a)
        assert success_a is True

        # Second acquire by user B should fail
        lock_data_b = {
            "locked": True,
            "session_id": "sess_B",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success_b = self.provider.acquire_lock(lock_data_b)
        assert success_b is False

        # Verify remote lock still owned by A
        status = self.provider.remote_lock_status()
        assert status["session_id"] == "sess_A"

        self.provider.release_lock("user_a")

    # ---- Test F: Release ----
    def test_release_keeps_main_unchanged_and_removes_lock(self):
        lock_data = {
            "locked": True,
            "session_id": "sess_789",
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        before_head = get_main_head(self.repo_path)
        before_status = get_main_status(self.repo_path)
        before_branch = get_main_branch(self.repo_path)

        success = self.provider.acquire_lock(lock_data)
        assert success is True
        assert remote_lock_exists(self.remote_path) is True

        release_success = self.provider.release_lock("test_user")
        assert release_success is True

        after_head = get_main_head(self.repo_path)
        after_status = get_main_status(self.repo_path)
        after_branch = get_main_branch(self.repo_path)

        assert after_head == before_head
        assert after_status == before_status
        assert after_branch == before_branch
        assert remote_lock_exists(self.remote_path) is False, "lock-main should be deleted"

    # ---- Test G: Atomic Race ----
    def test_atomic_race_two_contenders(self):
        """Two threads attempt to acquire simultaneously. Exactly one wins."""
        results = []
        lock = threading.Lock()

        def acquire_worker(worker_id: str):
            try:
                lock_data = {
                    "locked": True,
                    "session_id": f"sess_{worker_id}",
                    "owner": f"user_{worker_id}",
                    "username": f"user_{worker_id}",
                    "user_id": f"user_{worker_id}",
                    "acquired_at": datetime.now().isoformat(),
                    "last_heartbeat": datetime.now().isoformat(),
                    "machine": "test_machine",
                }
                # Each worker creates its own provider instance to simulate separate machines
                provider = GitSynchronizationProvider(
                    repo_path=self.repo_path,
                    repository_url=str(self.remote_path),
                    token="",
                    branch="main"
                )
                provider.connect()
                success = provider.acquire_lock(lock_data)
                with lock:
                    results.append((worker_id, success))
                if success:
                    # Keep lock for a moment to ensure the other fails
                    time.sleep(0.5)
                    provider.release_lock(f"user_{worker_id}")
            except Exception as e:
                with lock:
                    results.append((worker_id, f"ERROR: {e}"))

        # Run multiple rounds for reliability
        rounds = 10
        for round_num in range(rounds):
            results.clear()
            threads = []
            for i in range(2):
                t = threading.Thread(target=acquire_worker, args=(str(i),))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=10)

            successes = [r for r in results if r[1] is True]
            failures = [r for r in results if r[1] is False]
            assert len(successes) == 1, f"Expected 1 winner, got {len(successes)} in round {round_num}"
            assert len(failures) == 1, f"Expected 1 loser, got {len(failures)} in round {round_num}"

            # Verify final remote state has exactly one owner
            status = self.provider.remote_lock_status()
            if status["locked"]:
                # If someone is still holding the lock, release it (should be the winner's session)
                winner_id = successes[0][0]
                self.provider.release_lock(f"user_{winner_id}")
            # Ensure lock is gone for next round
            time.sleep(0.2)

    # ---- Test H: Failed Acquisition Does Not Touch MAIN ----
    def test_failed_acquisition_does_not_touch_main(self):
        # First acquire by user A
        lock_data_a = {
            "locked": True,
            "session_id": "sess_A",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success_a = self.provider.acquire_lock(lock_data_a)
        assert success_a is True

        # Record MAIN state for user B (loser)
        before_head_b = get_main_head(self.repo_path)
        before_status_b = get_main_status(self.repo_path)
        before_branch_b = get_main_branch(self.repo_path)

        # Attempt acquire by user B (should fail)
        lock_data_b = {
            "locked": True,
            "session_id": "sess_B",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        # Create a separate provider for B
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(self.remote_path),
            token="",
            branch="main"
        )
        provider_b.connect()
        success_b = provider_b.acquire_lock(lock_data_b)
        assert success_b is False

        after_head_b = get_main_head(self.repo_path)
        after_status_b = get_main_status(self.repo_path)
        after_branch_b = get_main_branch(self.repo_path)

        assert after_head_b == before_head_b, "Loser's MAIN HEAD changed"
        assert after_status_b == before_status_b, "Loser's MAIN working tree changed"
        assert after_branch_b == before_branch_b, "Loser's MAIN branch changed"

        # Cleanup
        self.provider.release_lock("user_a")