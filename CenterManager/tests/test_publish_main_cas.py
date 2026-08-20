# -*- coding: utf-8 -*-
"""Provider-level MAIN publish fencing tests."""

import json
import subprocess
from pathlib import Path

import pytest

from centermanager.platform.synchronization.git_synchronization_provider import (
    GitSynchronizationProvider,
)
from centermanager.platform.synchronization.exceptions import PushFailedError


def _clone(remote: Path, path: Path) -> GitSynchronizationProvider:
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
    assert provider.connect()
    return provider


def _remote_head(remote: Path) -> str:
    out = subprocess.check_output(
        ["git", "ls-remote", str(remote), "refs/heads/main"], text=True
    ).strip()
    return out.split()[0]


def test_publish_only_main_cas_rejects_remote_change(seeded_center_manager_remote, tmp_path):
    """A stale writer must not overwrite a newer remote MAIN commit."""
    remote = seeded_center_manager_remote
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    provider_a = _clone(remote, repo_a)
    provider_b = _clone(remote, repo_b)

    expected = _remote_head(remote)

    # A prepares a business change locally.
    manifest_a = repo_a / "manifest.json"
    data_a = json.loads(manifest_a.read_text(encoding="utf-8"))
    data_a["runtime_version"] = 2
    manifest_a.write_text(json.dumps(data_a, indent=2), encoding="utf-8")

    # B publishes first.
    manifest_b = repo_b / "manifest.json"
    data_b = json.loads(manifest_b.read_text(encoding="utf-8"))
    data_b["runtime_version"] = 99
    manifest_b.write_text(json.dumps(data_b, indent=2), encoding="utf-8")
    assert provider_b.publish_only("B wins", "user_b", expected_main_commit=expected)
    winner = _remote_head(remote)

    # A must fail at the final MAIN fence. It must not pull/rebase or overwrite B.
    with pytest.raises(PushFailedError):
        provider_a.publish_only("A stale", "user_a", expected_main_commit=expected)

    assert _remote_head(remote) == winner

    verify = tmp_path / "verify"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote), str(verify)],
        check=True,
        capture_output=True,
        text=True,
    )
    remote_manifest = json.loads((verify / "manifest.json").read_text(encoding="utf-8"))
    assert remote_manifest["runtime_version"] == 99
