# -*- coding: utf-8 -*-
"""Real provider-level tests for GitSynchronizationProvider.publish_only()."""

import pytest
import subprocess
import json
from pathlib import Path
from unittest.mock import patch

from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


class TestPublishOnlyProvider:
    def test_real_git_provider_publish_only_commits_and_pushes_without_remote_sync(
        self, fresh_center_manager_remote, tmp_path
    ):
        """
        Real integration test for GitSynchronizationProvider.publish_only().
        Uses a real bare remote and executes the real provider implementation.
        Verifies:
        - commit and push succeed
        - remote receives the change
        - no fetch/pull/rebase/merge/reset are performed
        """
        # Clone from remote to local repo
        repo_path = tmp_path / "repo"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(fresh_center_manager_remote), str(repo_path)],
            check=True
        )

        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(fresh_center_manager_remote),
            token="",
            branch="main"
        )
        provider.connect()

        # Modify manifest locally
        manifest_path = repo_path / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        old_version = manifest.get("runtime_version", 0)
        new_version = old_version + 1
        manifest["runtime_version"] = new_version
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Capture Git commands without preventing execution
        commands = []
        original_run = provider._run_git_command

        def capture_run(args, cwd=None):
            commands.append(args)
            return original_run(args, cwd=cwd)

        with patch.object(provider, "_run_git_command", side_effect=capture_run):
            result = provider.publish_only("Test real publish-only", "test_user")

        assert result is True, "publish_only() should return True on success"

        # Verify remote received the change
        verify_path = tmp_path / "verify"
        subprocess.run(
            # FIX: add --branch main to ensure checkout
            ["git", "clone", "--branch", "main", str(fresh_center_manager_remote), str(verify_path)],
            check=True
        )
        with open(verify_path / "manifest.json", "r", encoding="utf-8") as f:
            verify_manifest = json.load(f)
        assert verify_manifest.get("runtime_version") == new_version, (
            f"Remote manifest version should be {new_version}, got {verify_manifest.get('runtime_version')}"
        )

        # Verify no remote synchronization commands were executed
        command_strings = [" ".join(cmd) for cmd in commands]

        assert not any("fetch" in cmd for cmd in command_strings), "fetch should not be called"
        assert not any("pull" in cmd for cmd in command_strings), "pull should not be called"
        assert not any("rebase" in cmd for cmd in command_strings), "rebase should not be called"
        assert not any("merge" in cmd for cmd in command_strings), "merge should not be called"
        assert not any("reset" in cmd for cmd in command_strings), "reset should not be called"

        # But commit and push must be present
        assert any("commit" in cmd for cmd in command_strings), "commit must be called"
        assert any("push" in cmd for cmd in command_strings), "push must be called"