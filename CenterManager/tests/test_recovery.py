# -*- coding: utf-8 -*-
import pytest
from pathlib import Path

from centermanager.platform.collaboration.recovery_manager import RecoveryManager
from centermanager.platform.collaboration.lock_manager import LockManager
from centermanager.platform.collaboration.json_lock_repository import JsonLockRepository
from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
from centermanager.events.event_bus import EventBus


@pytest.fixture
def metadata_dir(tmp_path):
    return tmp_path / "metadata"


def test_recovery_stale_lock(metadata_dir):
    lock_repo = JsonLockRepository(metadata_dir / "lock.json")
    meta_repo = JsonMetadataRepository(metadata_dir)

    # Create a stale lock
    lock_repo.save_lock({
        "locked": True,
        "owner": "test_owner",
        "session_id": "sess_123",
        "started_at": "2026-01-01T00:00:00",
        "last_heartbeat": "2026-01-01T00:00:00",
        "heartbeat_version": 1,
    })

    lock_manager = LockManager(lock_repo, timeout_seconds=10)
    event_bus = EventBus()
    recovery = RecoveryManager(lock_manager, meta_repo, event_bus)

    report = recovery.inspect_and_recover()
    assert report["lock_recovered"] is True
    assert report["recovered"] is True

    # Lock should be released
    assert not lock_manager.is_locked()