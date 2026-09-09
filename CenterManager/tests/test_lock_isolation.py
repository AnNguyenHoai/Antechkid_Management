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
        if remote_lock_exists(self.remote_path):
            subprocess.run(
                ["git", "push", str(self.remote_path), "--delete", "lock-main", "--force"],
                capture_output=True
            )

    def test_acquire_keeps_main_head_unchanged(self):
        before_head = get_main_head(self.repo_path)
        lock_data = {
            "locked": True, "session_id": "sess_123", "owner": "test_user",
            "username": "test_user", "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(), "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data) is True
        assert get_main_head(self.repo_path) == before_head
        self.provider.release_lock("test_user")

    def test_acquire_keeps_main_working_tree_clean(self):
        before_status = get_main_status(self.repo_path)
        assert before_status == ""
        lock_data = {
            "locked": True, "session_id": "sess_123", "owner": "test_user",
            "username": "test_user", "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(), "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data) is True
        assert get_main_status(self.repo_path) == before_status
        self.provider.release_lock("test_user")

    def test_acquire_keeps_main_branch_unchanged(self):
        before_branch = get_main_branch(self.repo_path)
        assert before_branch == "main", "Initial branch should be main"
        lock_data = {
            "locked": True, "session_id": "sess_123", "owner": "test_user",
            "username": "test_user", "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(), "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data) is True
        assert get_main_branch(self.repo_path) == before_branch
        self.provider.release_lock("test_user")

    def test_remote_lock_created_and_verified(self):
        assert remote_lock_exists(self.remote_path) is False, "lock-main should not exist initially"
        session_id = "sess_456"
        lock_data = {
            "locked": True, "session_id": session_id, "owner": "test_user",
            "username": "test_user", "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(), "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data) is True
        assert remote_lock_exists(self.remote_path) is True, "lock-main should exist after acquire"
        status = self.provider.remote_lock_status()
        assert status["locked"] is True
        assert status["session_id"] == session_id
        assert status["owner"] == "test_user"
        self.provider.release_lock("test_user")

    def test_acquisition_fails_if_lock_held_by_other(self):
        lock_data_a = {
            "locked": True, "session_id": "sess_A", "owner": "user_a", "username": "user_a",
            "user_id": "user_a", "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(), "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data_a) is True
        lock_data_b = {
            "locked": True, "session_id": "sess_B", "owner": "user_b", "username": "user_b",
            "user_id": "user_b", "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(), "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data_b) is False
        assert self.provider.remote_lock_status()["session_id"] == "sess_A"
        self.provider.release_lock("user_a")

    def test_release_keeps_main_unchanged_and_removes_lock(self):
        lock_data = {
            "locked": True, "session_id": "sess_789", "owner": "test_user",
            "username": "test_user", "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(), "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        before_head = get_main_head(self.repo_path)
        before_status = get_main_status(self.repo_path)
        before_branch = get_main_branch(self.repo_path)
        assert self.provider.acquire_lock(lock_data) is True
        assert remote_lock_exists(self.remote_path) is True
        assert self.provider.release_lock("test_user") is True
        assert get_main_head(self.repo_path) == before_head
        assert get_main_status(self.repo_path) == before_status
        assert get_main_branch(self.repo_path) == before_branch
        assert remote_lock_exists(self.remote_path) is False, "lock-main should be deleted"

    # ---- Test G: Atomic Race ----
    def test_atomic_race_two_contenders(self):
        """Two threads attempt to acquire simultaneously. Exactly one wins per round."""
        rounds = 10
        for round_num in range(rounds):
            results = []
            result_lock = threading.Lock()
            start_barrier = threading.Barrier(2)
            attempt_complete_barrier = threading.Barrier(2)

            def acquire_worker(worker_id: str):
                provider = None
                success = False
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
                    provider = GitSynchronizationProvider(
                        repo_path=self.repo_path,
                        repository_url=str(self.remote_path),
                        token="",
                        branch="main"
                    )
                    provider.connect()
                    start_barrier.wait(timeout=10)
                    success = provider.acquire_lock(lock_data)
                    with result_lock:
                        results.append((worker_id, success))
                except Exception as e:
                    with result_lock:
                        results.append((worker_id, f"ERROR: {e}"))
                finally:
                    try:
                        attempt_complete_barrier.wait(timeout=10)
                    except threading.BrokenBarrierError:
                        pass
                    if success and provider is not None:
                        provider.release_lock(f"user_{worker_id}")

            threads = [threading.Thread(target=acquire_worker, args=(str(i),)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)

            assert all(not thread.is_alive() for thread in threads), f"Contender thread leaked in round {round_num}"
            successes = [r for r in results if r[1] is True]
            failures = [r for r in results if r[1] is False]
            assert len(successes) == 1, f"Expected 1 winner, got {len(successes)} in round {round_num}"
            assert len(failures) == 1, f"Expected 1 loser, got {len(failures)} in round {round_num}"

            status = self.provider.remote_lock_status()
            if status["locked"]:
                winner_id = successes[0][0]
                self.provider.release_lock(f"user_{winner_id}")
            time.sleep(0.2)

    def test_failed_acquisition_does_not_touch_main(self):
        lock_data_a = {
            "locked": True, "session_id": "sess_A", "owner": "user_a", "username": "user_a",
            "user_id": "user_a", "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(), "machine": "test_machine",
        }
        assert self.provider.acquire_lock(lock_data_a) is True
        before_head_b = get_main_head(self.repo_path)
        before_status_b = get_main_status(self.repo_path)
        before_branch_b = get_main_branch(self.repo_path)
        lock_data_b = {
            "locked": True, "session_id": "sess_B", "owner": "user_b", "username": "user_b",
            "user_id": "user_b", "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(), "machine": "test_machine",
        }
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path, repository_url=str(self.remote_path), token="", branch="main"
        )
        provider_b.connect()
        assert provider_b.acquire_lock(lock_data_b) is False
        assert get_main_head(self.repo_path) == before_head_b, "Loser's MAIN HEAD changed"
        assert get_main_status(self.repo_path) == before_status_b, "Loser's MAIN working tree changed"
        assert get_main_branch(self.repo_path) == before_branch_b, "Loser's MAIN branch changed"
        self.provider.release_lock("user_a")
