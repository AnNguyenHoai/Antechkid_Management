# -*- coding: utf-8 -*-
"""Regression tests for the cross-machine shared WRITE queue hardening."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization.git_synchronization_provider import (
    GitSynchronizationProvider,
)


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _seed_remote(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git executable is required")

    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git("init", "--bare", cwd=remote)

    source = tmp_path / "source"
    source.mkdir()
    _git("init", cwd=source)
    _git("config", "user.name", "Test", cwd=source)
    _git("config", "user.email", "test@example.com", cwd=source)
    (source / "README.md").write_text("# collaboration test\n", encoding="utf-8")
    (source / "manifest.json").write_text(
        json.dumps({"runtime_version": 1}),
        encoding="utf-8",
    )
    _git("branch", "-M", "main", cwd=source)
    _git("add", ".", cwd=source)
    _git("commit", "-m", "seed", cwd=source)
    _git("remote", "add", "origin", str(remote), cwd=source)
    _git("push", "-u", "origin", "main", cwd=source)
    return remote


def _make_machine(tmp_path: Path, remote: Path, name: str):
    runtime = tmp_path / f"runtime_{name}"
    runtime.mkdir()
    repo = runtime / "repository"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote), str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git("config", "user.name", f"User {name}", cwd=repo)
    _git("config", "user.email", f"{name}@example.com", cwd=repo)
    provider = GitSynchronizationProvider(
        repo_path=repo,
        repository_url=str(remote),
        branch="main",
    )
    assert provider.connect()
    manager = CollaborationManager(
        runtime_root=runtime,
        event_bus=EventBus(),
        sync_provider=provider,
    )
    manager.initialize(name, f"User {name}", "admin")
    return manager, provider


def test_separate_runtimes_observe_one_authoritative_remote_queue(tmp_path):
    remote = _seed_remote(tmp_path)
    cm_a, _ = _make_machine(tmp_path, remote, "A")
    cm_b, _ = _make_machine(tmp_path, remote, "B")

    try:
        assert cm_a.request_write().is_granted
        request_b = cm_b.request_write()
        assert request_b.is_waiting

        queue_seen_by_a = cm_a.get_queue()
        queue_seen_by_b = cm_b.get_queue()

        assert queue_seen_by_a["length"] == 1
        assert queue_seen_by_b["length"] == 1
        assert queue_seen_by_a["next"]["request_id"] == request_b.request_id
        assert queue_seen_by_a["next"]["username"] == "User B"
        assert queue_seen_by_b["next"]["request_id"] == request_b.request_id
    finally:
        cm_b.cancel_waiting_request()
        if cm_a.is_writing():
            cm_a.release_write()
        cm_a.shutdown()
        cm_b.shutdown()


def test_waiting_request_renewal_updates_remote_queue_lease(tmp_path):
    remote = _seed_remote(tmp_path)
    cm_a, _ = _make_machine(tmp_path, remote, "A")
    cm_b, provider_b = _make_machine(tmp_path, remote, "B")

    try:
        assert cm_a.request_write().is_granted
        request_b = cm_b.request_write()
        assert request_b.is_waiting

        # Re-age the request close to the 120-second TTL without crossing it.
        old_timestamp = (datetime.now() - timedelta(seconds=110)).isoformat()

        def age_request(requests):
            for request in requests:
                if request.get("request_id") == request_b.request_id:
                    request["timestamp"] = old_timestamp
                    return True, requests
            return False, requests

        assert provider_b._mutate_remote_queue(age_request)
        before = provider_b.remote_queue_status()["next"]
        assert before["timestamp"] == old_timestamp

        assert cm_b.refresh_waiting_request(request_b.request_id)
        after = provider_b.remote_queue_status()["next"]
        refreshed_at = datetime.fromisoformat(after["timestamp"])

        assert (datetime.now() - refreshed_at).total_seconds() < 10
        assert after["enqueue_timestamp"] == before["enqueue_timestamp"]
    finally:
        cm_b.cancel_waiting_request()
        if cm_a.is_writing():
            cm_a.release_write()
        cm_a.shutdown()
        cm_b.shutdown()


def test_cancel_is_idempotent_after_waiting_request_disappears(tmp_path):
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=EventBus())
    cm.initialize("A", "User A", "admin")
    try:
        # No pending request is equivalent to an already-expired/cancelled queue entry.
        assert cm.cancel_waiting_request() is True
    finally:
        cm.shutdown()


def test_poller_renews_waiting_request_and_allows_expired_lock_handoff_contract():
    poller = _source("platform/collaboration/poller.py")

    assert "if self._cm.has_pending_waiting_request():" in poller
    assert "self._cm.refresh_waiting_request()" in poller
    assert 'and not self._cm._is_lock_stale(remote_lock)' in poller


def test_main_window_reconciles_missing_authoritative_waiting_request():
    source = _source("ui/main_window.py")

    assert "def _reconcile_waiting_transaction(" in source
    assert "self._transaction.cancel_waiting(" in source
    assert "Authoritative WRITE queue no longer contains this request" in source
    assert "self._transaction._waiting_position = index" in source


def test_remote_queue_isolated_from_main_business_branch():
    provider = _source(
        "platform/synchronization/git_synchronization_provider.py"
    )

    assert 'self._queue_branch = f"queue-{branch}"' in provider
    assert 'f"{commit_sha}:refs/heads/{self._queue_branch}"' in provider
    assert '"queue.json"' in provider
    assert "remote_queue_status" in provider
