# -*- coding: utf-8 -*-
"""Performance Phase 1 contracts for Start/Finish Editing."""
from pathlib import Path
from types import SimpleNamespace

from centermanager.platform.synchronization.synchronization_manager import (
    SynchronizationManager,
    SynchronizationResult,
    SyncResult,
)


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_authoritative_handoff_reuses_fetched_main_and_lightweight_recheck():
    source = _read(
        "src/centermanager/platform/sync/authoritative_runtime_sync_service.py"
    )
    barrier = source.split(
        "def _force_latest_main_repository", 1
    )[1].split("def execute_write_handoff_sync", 1)[0]
    handoff = source.split(
        "def execute_write_handoff_sync", 1
    )[1].split("def _perform_sync", 1)[0]

    assert "provider.health()" not in barrier
    assert "get_fetched_remote_main_commit" in barrier
    assert "observe_remote_main_commit" in handoff
    assert "self._last_write_handoff_main_commit = authoritative_commit" in handoff


def test_write_transaction_reuses_handoff_commit_for_base_fence():
    source = _read("src/centermanager/services/write_transaction.py")
    start = source.split("def start_editing", 1)[1].split(
        "def finish_editing", 1
    )[0]

    assert "self._get_handoff_main_commit()" in start
    assert "PERF start_edit" in start


def test_finish_reuses_authority_generation_and_lightweight_main_observation():
    source = _read("src/centermanager/services/write_transaction.py")
    finish = source.split("def enter_finishing", 1)[1].split(
        "def refresh_finishing_authority", 1
    )[0]

    assert 'current_gen = int(auth.get("generation", 0) or 0)' in finish
    assert "observe_remote_main_commit" in finish
    assert "PERF finish_edit" in source


class _Provider:
    def __init__(self):
        self.materialized_calls = 0
        self.published = False

    def name(self):
        return "fake"

    def health(self):
        return True

    def connect(self):
        return True

    def publish_only(self, message, user, expected_main_commit=None):
        self.published = True
        return True


def test_publish_only_can_skip_duplicate_runtime_db_materialization(monkeypatch):
    provider = _Provider()
    manager = SynchronizationManager(provider=provider)

    monkeypatch.setattr(manager, "_prepare_local_repository", lambda: True)

    import centermanager.platform.synchronization.synchronization_manager as module

    calls = []
    monkeypatch.setattr(
        module,
        "materialize_runtime_database_to_repository",
        lambda: calls.append("materialize"),
    )

    result = manager.publish_only(
        message="Finish Editing",
        user="tester",
        expected_main_commit="abc",
        repository_already_materialized=True,
    )

    assert result.is_success()
    assert calls == []
    assert provider.published is True


def test_normal_publish_path_still_materializes_when_not_prepared(monkeypatch):
    provider = _Provider()
    manager = SynchronizationManager(provider=provider)

    monkeypatch.setattr(manager, "_prepare_local_repository", lambda: True)

    import centermanager.platform.synchronization.synchronization_manager as module

    calls = []
    monkeypatch.setattr(
        module,
        "materialize_runtime_database_to_repository",
        lambda: calls.append("materialize"),
    )

    result = manager.publish_only(
        message="manual",
        user="tester",
        expected_main_commit="abc",
    )

    assert result.is_success()
    assert calls == ["materialize"]


def test_poller_can_pause_observation_without_disabling_lease_contract():
    source = _read("src/centermanager/platform/collaboration/poller.py")

    assert "def pause_observation" in source
    assert "def resume_observation" in source
    assert "if self._observation_paused:" in source
    # Lease renewal has its own timer/path and must remain independent.
    assert "def _renew_active_lease" in source
