# -*- coding: utf-8 -*-
"""Tests for collaboration state isolation from MAIN business repository."""

import pytest
import subprocess
import json
import tempfile
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


def get_main_status(repo_path: Path) -> str:
    """Return git status --porcelain for MAIN."""
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def get_main_head(repo_path: Path) -> str:
    """Return the current MAIN HEAD SHA."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
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


def create_collaboration_state(runtime_root: Path, session_id: str = "test_session") -> Path:
    """Create a collaboration state file in runtime/collaboration/."""
    collab_dir = runtime_root / "collaboration"
    collab_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_dir = collab_dir / "heartbeat"
    heartbeat_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_file = heartbeat_dir / f"{session_id}.json"
    heartbeat_data = {
        "session_id": session_id,
        "machine_fingerprint": "test_machine",
        "user_id": "test_user",
        "username": "test_user",
        "last_seen": datetime.now().isoformat(),
        "runtime_version": 1,
        "is_active": True,
    }
    with open(heartbeat_file, "w", encoding="utf-8") as f:
        json.dump(heartbeat_data, f, indent=2)

    # Also create a session state file
    session_file = collab_dir / "session.json"
    session_data = {
        "session_id": session_id,
        "user_id": "test_user",
        "username": "test_user",
        "mode": "READ",
        "started_at": datetime.now().isoformat(),
    }
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    return heartbeat_file


class TestCollaborationIsolation:
    """Test suite validating collaboration state isolation from MAIN."""

    @pytest.fixture(autouse=True)
    def setup_repo(self, seeded_remote, tmp_path):
        """Clone the seeded remote and set up runtime structure."""
        # MAIN repository
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

        # Runtime root (outside the repository)
        self.runtime_root = tmp_path / "runtime"
        self.runtime_root.mkdir(parents=True, exist_ok=True)

        self.remote_path = seeded_remote

        self.provider = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(seeded_remote),
            token="",
            branch="main"
        )
        self.provider.connect()

        yield

        # Cleanup: delete lock branch if left
        if remote_lock_exists(self.remote_path):
            subprocess.run(
                ["git", "push", str(self.remote_path), "--delete", "lock-main", "--force"],
                capture_output=True
            )

    # ---- Test A: Collaboration Runtime Outside MAIN ----
    def test_collaboration_runtime_outside_main(self):
        """Verify collaboration state is written outside MAIN working tree."""
        # Write collaboration state
        heartbeat_file = create_collaboration_state(self.runtime_root, "sess_001")

        # Verify path is outside the repository
        assert str(heartbeat_file).startswith(str(self.runtime_root))
        assert not str(heartbeat_file).startswith(str(self.repo_path))

        # Verify the file exists
        assert heartbeat_file.exists()

        # Verify MAIN git status is clean
        status = get_main_status(self.repo_path)
        assert status == "", "MAIN working tree should be clean"

    # ---- Test B: MAIN Publish Does Not Stage Collaboration State ----
    def test_publish_does_not_stage_collaboration(self):
        """Verify that publish() does not stage collaboration state."""
        # Create business change
        business_file = self.repo_path / "business.txt"
        business_file.write_text("Business data")

        # Create collaboration state
        create_collaboration_state(self.runtime_root, "sess_002")

        # Stage business file
        subprocess.run(["git", "add", "business.txt"], cwd=self.repo_path, check=True)

        # Publish (this will add all changes and commit)
        result = self.provider.publish("Test business publish", "test_user")
        assert result is True

        # Inspect the commit
        commit_files = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )

        # Should NOT contain any collaboration files
        assert "collaboration" not in commit_files.stdout
        assert "heartbeat" not in commit_files.stdout
        assert "session.json" not in commit_files.stdout

        # Should contain the business file
        assert "business.txt" in commit_files.stdout

    # ---- Test C: Collaboration State Survives Publish ----
    def test_collaboration_state_survives_publish(self):
        """Verify collaboration state persists after MAIN publish."""
        # Create collaboration state
        heartbeat_file = create_collaboration_state(self.runtime_root, "sess_003")
        assert heartbeat_file.exists()

        # Create business change
        business_file = self.repo_path / "business2.txt"
        business_file.write_text("Another business data")

        # Publish
        result = self.provider.publish("Test publish with collaboration state", "test_user")
        assert result is True

        # Verify collaboration state still exists
        assert heartbeat_file.exists()

        # Verify content is intact
        with open(heartbeat_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["session_id"] == "sess_003"
        assert data["username"] == "test_user"

    # ---- Test D: MAIN Status Isolation ----
    def test_main_status_isolation(self):
        """Verify collaboration changes do not appear in git status."""
        # Create collaboration state
        create_collaboration_state(self.runtime_root, "sess_004")

        # git status should not show collaboration files
        status = get_main_status(self.repo_path)
        assert status == "", "MAIN git status should be clean"

        # Create business change and stage it
        business_file = self.repo_path / "business3.txt"
        business_file.write_text("Business data 3")
        subprocess.run(["git", "add", "business3.txt"], cwd=self.repo_path, check=True)

        # git status should show only the business file
        status = get_main_status(self.repo_path)
        assert "business3.txt" in status
        assert "collaboration" not in status
        assert "heartbeat" not in status

    # ---- Test E: No Collaboration Files In MAIN Commit ----
    def test_no_collaboration_in_main_commit(self):
        """Verify MAIN commit contains only business files."""
        # Create collaboration state
        create_collaboration_state(self.runtime_root, "sess_005")

        # Create business change
        business_file = self.repo_path / "business4.txt"
        business_file.write_text("Business data 4")

        # Publish
        result = self.provider.publish("Test commit isolation", "test_user")
        assert result is True

        # Use git ls-tree to inspect the commit tree
        tree_output = subprocess.run(
            ["git", "ls-tree", "-r", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )

        # Should contain business.txt
        assert "business4.txt" in tree_output.stdout

        # Should NOT contain any collaboration files
        assert "collaboration" not in tree_output.stdout
        assert "heartbeat" not in tree_output.stdout
        assert "session.json" not in tree_output.stdout

    # ---- Test F: Lock Regression ----
    def test_lock_works_with_isolation(self):
        """Verify lock operations still work with collaboration isolation."""
        # Lock acquisition should not be affected
        lock_data = {
            "locked": True,
            "session_id": "sess_lock",
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }

        # Acquire lock
        success = self.provider.acquire_lock(lock_data)
        assert success is True

        # Verify remote lock exists
        assert remote_lock_exists(self.remote_path) is True

        # Verify MAIN is clean
        status = get_main_status(self.repo_path)
        assert status == "", "MAIN should be clean after lock acquisition"

        # Release lock
        release_success = self.provider.release_lock("test_user")
        assert release_success is True

        # Verify lock is gone
        assert remote_lock_exists(self.remote_path) is False

        # Verify MAIN is still clean
        status = get_main_status(self.repo_path)
        assert status == "", "MAIN should be clean after lock release"

    # ---- Test G: Publish After Lock ----
    def test_publish_after_lock_does_not_include_collaboration(self):
        """Verify publishing after lock operations still excludes collaboration."""
        # Acquire lock
        lock_data = {
            "locked": True,
            "session_id": "sess_lock2",
            "owner": "test_user",
            "username": "test_user",
            "user_id": "test_user",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data)

        # Create business change
        business_file = self.repo_path / "business_after_lock.txt"
        business_file.write_text("Business after lock")

        # Create collaboration state (should be ignored)
        create_collaboration_state(self.runtime_root, "sess_lock2")

        # Publish
        result = self.provider.publish("Publish after lock", "test_user")
        assert result is True

        # Inspect commit
        commit_files = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )

        assert "business_after_lock.txt" in commit_files.stdout
        assert "collaboration" not in commit_files.stdout
        assert "heartbeat" not in commit_files.stdout

        # Release lock
        self.provider.release_lock("test_user")