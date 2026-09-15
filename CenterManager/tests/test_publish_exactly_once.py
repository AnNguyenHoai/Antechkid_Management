# -*- coding: utf-8 -*-
"""Regression tests for exactly-once MAIN publish semantics."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from centermanager.platform.synchronization.git_synchronization_provider import (
    GitSynchronizationProvider,
)
from centermanager.platform.synchronization.exceptions import PushFailedError


def _clone_provider(remote: Path, path: Path) -> GitSynchronizationProvider:
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote), str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)

    provider = GitSynchronizationProvider(
        repo_path=path,
        repository_url=str(remote),
        token="",
        branch="main",
    )
    # These tests exercise the real Git command path. GitPython is optional in
    # the provider; avoid coupling this regression suite to its presence.
    provider._connected = True
    # The provider's real Git operations use subprocess, but _push_only()
    # requires only the presence of an `origin` remote at this boundary.
    # Do not use object() here: _has_remote_origin() must evaluate to True.
    provider._repo = SimpleNamespace(
        remotes=[SimpleNamespace(name="origin")]
    )
    return provider


def _remote_head(remote: Path) -> str:
    out = subprocess.check_output(
        ["git", "ls-remote", str(remote), "refs/heads/main"], text=True
    ).strip()
    return out.split()[0]


def _remote_version(remote: Path, tmp_path: Path, name: str) -> int:
    verify = tmp_path / name
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote), str(verify)],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads((verify / "manifest.json").read_text(encoding="utf-8"))
    return int(manifest["runtime_version"])


def _prepare_manifest(provider: GitSynchronizationProvider, version: int) -> None:
    path = provider._repo_path / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["runtime_version"] = version
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_successful_publish_pushes_once(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    commands = []
    original = provider._run_git_command

    def capture(args, cwd=None, check=True, env=None):
        commands.append(list(args))
        return original(args, cwd=cwd, check=check, env=env)

    with patch.object(provider, "_run_git_command", side_effect=capture):
        assert provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)

    push_calls = [c for c in commands if c and c[0] == "push"]
    commit_calls = [c for c in commands if c and c[0] == "commit"]

    assert len(push_calls) == 1
    assert len(commit_calls) == 1
    assert _remote_head(fresh_center_manager_remote) != expected
    assert _remote_version(fresh_center_manager_remote, tmp_path, "verify") == 2


def test_successful_publish_creates_one_main_commit(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    old = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    provider.publish_only("Finish Editing", "user_a", expected_main_commit=old)
    new = _remote_head(fresh_center_manager_remote)

    assert new != old
    count = subprocess.check_output(
        ["git", "rev-list", "--count", f"{old}..{new}"],
        cwd=provider._repo_path,
        text=True,
    ).strip()
    assert count == "1"


def test_publish_does_not_push_twice(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    push_calls = []
    original = provider._run_git_command

    def capture(args, cwd=None, check=True, env=None):
        if args and args[0] == "push":
            push_calls.append(list(args))
        return original(args, cwd=cwd, check=check, env=env)

    with patch.object(provider, "_run_git_command", side_effect=capture):
        assert provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)

    assert len(push_calls) == 1


def test_publish_increments_remote_version_once(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    before = _remote_version(fresh_center_manager_remote, tmp_path, "before")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, before + 1)

    assert provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)

    after = _remote_version(fresh_center_manager_remote, tmp_path, "after")
    assert after == before + 1


def test_failed_push_does_not_report_publish_success(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    # The expected remote commit is deliberately stale before publish.
    other = _clone_provider(fresh_center_manager_remote, tmp_path / "other")
    _prepare_manifest(other, 99)
    assert other.publish_only("B wins", "user_b", expected_main_commit=expected)
    winner = _remote_head(fresh_center_manager_remote)

    with patch.object(provider, "_push_only", side_effect=PushFailedError("simulated push failure")):
        with pytest.raises(PushFailedError):
            provider.publish_only("A stale", "user_a", expected_main_commit=winner)

    # No successful publish can be claimed by provider.publish_only().
    # Remote must remain at the winner commit.
    assert _remote_head(fresh_center_manager_remote) == winner


def test_retry_does_not_duplicate_successful_publish(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    calls = {"count": 0}
    original_push = provider._push_only

    def fail_once(expected_remote_commit=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PushFailedError("transient push failure")
        return original_push(expected_remote_commit=expected_remote_commit)

    with patch.object(provider, "_push_only", side_effect=fail_once):
        with pytest.raises(PushFailedError):
            provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)
        # The retry must push the already-created local MAIN commit. It must
        # not create a second commit and must not report success without push.
        assert provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)

    assert calls["count"] == 2
    assert _remote_version(fresh_center_manager_remote, tmp_path, "retry_verify") == 2
    local_commits = subprocess.check_output(
        ["git", "rev-list", "--count", f"{expected}..HEAD"],
        cwd=provider._repo_path,
        text=True,
    ).strip()
    assert local_commits == "1"



def test_publish_emits_one_push_success_log(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    # Observe the provider's single logging boundary directly. This avoids
    # coupling the contract to pytest's global logging configuration when the
    # full suite has already installed application logging handlers.
    import centermanager.platform.synchronization.git_synchronization_provider as provider_module
    with patch.object(provider_module.logger, "info", wraps=provider_module.logger.info) as info_mock:
        provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)

    success_logs = [
        call for call in info_mock.call_args_list
        if call.args and call.args[0] == "Push-only successful"
    ]
    assert len(success_logs) == 1


def test_publish_does_not_stage_external_collaboration_runtime(fresh_center_manager_remote, tmp_path):
    provider = _clone_provider(fresh_center_manager_remote, tmp_path / "repo")
    expected = _remote_head(fresh_center_manager_remote)
    _prepare_manifest(provider, 2)

    runtime_collab = tmp_path / "runtime" / "collaboration"
    runtime_collab.mkdir(parents=True)
    (runtime_collab / "lock.json").write_text('{"owner":"user_a"}', encoding="utf-8")

    provider.publish_only("Finish Editing", "user_a", expected_main_commit=expected)

    tree = subprocess.check_output(
        ["git", "ls-tree", "-r", "HEAD"], cwd=provider._repo_path, text=True
    )
    assert "collaboration/" not in tree
    assert "lock.json" not in tree
