# -*- coding: utf-8 -*-
"""
TASK 3.3.4-B.0 — Publish / Lease Impact Audit

Audit-only tests. These tests intentionally do not change production behavior.
They guard the call boundaries relevant to the suspected publish/lease interaction.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from centermanager.platform.sync import RuntimeSyncService, SyncStatus
from centermanager.platform.synchronization import (
    GitSynchronizationProvider,
    SynchronizationResult,
    SyncResult,
)


def _init_remote(tmp_path: Path):
    remote = tmp_path / "remote.git"
    source = tmp_path / "source"
    clone = tmp_path / "clone"

    subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                   capture_output=True, text=True)

    source.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=source, check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Audit"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "audit@example.com"], cwd=source, check=True)

    (source / "README.md").write_text("audit\n", encoding="utf-8")
    (source / "manifest.json").write_text(
        json.dumps({"runtime_version": 1}, indent=2), encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=source, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=source, check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=source, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=source, check=True,
                   capture_output=True, text=True)

    subprocess.run(["git", "clone", "--branch", "main", str(remote), str(clone)],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Audit"], cwd=clone, check=True)
    subprocess.run(["git", "config", "user.email", "audit@example.com"], cwd=clone, check=True)

    return remote, source, clone


def _provider(clone, remote):
    provider = GitSynchronizationProvider(
        repo_path=clone,
        repository_url=str(remote),
        token="",
        branch="main",
        username="audit",
        email="audit@example.com",
    )
    assert provider.connect()
    return provider


def test_publish_only_does_not_invoke_lease_lifecycle(tmp_path):
    """
    Publish-only must not directly acquire, renew, or release collaboration
    leases. This guards the separation between MAIN publish and collaboration
    lock lifecycle.
    """
    remote, _, clone = _init_remote(tmp_path)
    provider = _provider(clone, remote)

    manifest = clone / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["runtime_version"] = 2
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    renew = Mock(return_value=True)
    release = Mock(return_value=True)
    acquire = Mock(return_value=True)

    with patch.object(provider, "renew_lock", renew), \
         patch.object(provider, "release_lock", release), \
         patch.object(provider, "acquire_lock", acquire):
        assert provider.publish_only("audit publish", "audit") is True

    renew.assert_not_called()
    release.assert_not_called()
    acquire.assert_not_called()


def test_publish_only_retry_path_does_not_invoke_lease_lifecycle(tmp_path):
    """
    Exercise the 3.3.4-A retry shape:
      commit -> push failure -> retry existing HEAD -> push success.

    The retry must remain a MAIN publish operation and must not touch the
    collaboration lease lifecycle.
    """
    remote, _, clone = _init_remote(tmp_path)
    provider = _provider(clone, remote)

    manifest = clone / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["runtime_version"] = 2
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=clone, text=True
    ).strip()

    push_calls = {"count": 0}

    def push_side_effect(*args, **kwargs):
        push_calls["count"] += 1
        if push_calls["count"] == 1:
            from centermanager.platform.synchronization.exceptions import PushFailedError
            raise PushFailedError("simulated transient push failure")
        return None

    renew = Mock(return_value=True)
    release = Mock(return_value=True)

    with patch.object(provider, "renew_lock", renew), \
         patch.object(provider, "release_lock", release), \
         patch.object(provider, "_push_only", side_effect=push_side_effect):
        try:
            provider.publish_only("audit retry", "audit", expected_main_commit=expected)
        except Exception:
            pass

        # The first call creates the local commit but fails to push.
        # The second call must push the already-created HEAD.
        assert push_calls["count"] == 1

        assert provider.publish_only(
            "audit retry", "audit", expected_main_commit=expected
        ) is True

    assert push_calls["count"] == 2
    renew.assert_not_called()
    release.assert_not_called()


def test_runtime_publish_success_has_one_explicit_sync_check():
    """
    Current RuntimeSyncService behavior has one explicit post-publish
    check_for_updates() call. This is an audit guard against accidental
    multiplication of the post-publish trigger.
    """
    sync_manager = Mock()
    sync_manager.publish_only.return_value = SynchronizationResult(
        result=SyncResult.SUCCESS,
        message="ok",
        provider="git",
    )

    collab = Mock()
    session = Mock()
    session.session_id = "audit-session"
    collab.get_session.return_value = session

    context = Mock()
    service = RuntimeSyncService(
        sync_manager=sync_manager,
        collab_manager=collab,
        context_manager=context,
        poll_interval=60,
    )
    service._get_repository_version = Mock(return_value=81)
    service.check_for_updates = Mock(return_value=False)

    assert service.publish_only("Finish Editing", "audit") is True

    sync_manager.publish_only.assert_called_once()
    service.check_for_updates.assert_called_once()


def test_writer_active_sync_defer_does_not_call_lease_renewal():
    """
    MAIN sync deferral while a writer is active must remain orthogonal to
    collaboration lease renewal. The current sync service does not call
    renew_lock on this path.
    """
    sync_manager = Mock()
    sync_manager.provider.return_value.health.return_value = True

    collab = Mock()
    session = Mock()
    session.session_id = "audit-session"
    collab.get_session.return_value = session
    collab.is_writing.return_value = True
    collab.get_queue.return_value = {"requests": []}
    collab.renew_lock = Mock(return_value=True)

    context = Mock()
    context.get_context.return_value.runtime.is_ready.return_value = True

    service = RuntimeSyncService(
        sync_manager=sync_manager,
        collab_manager=collab,
        context_manager=context,
        poll_interval=60,
    )
    service._pending_update = True
    service._current_version = 80
    service._remote_version = 81

    service._attempt_sync()

    collab.renew_lock.assert_not_called()
    sync_manager.begin_sync.assert_not_called()
