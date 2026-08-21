# -*- coding: utf-8 -*-
"""Tests for MAIN optimistic concurrency / lost-update protection."""

import pytest
from unittest.mock import patch, MagicMock, call

from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.events.event_bus import EventBus


@pytest.fixture
def collab_manager(tmp_path):
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")
    return cm


def test_publish_succeeds_when_main_generation_unchanged(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    base_commit = "abc123"
    tx._base_main_commit = base_commit

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = base_commit
        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            result = tx.enter_finishing()
            assert result["success"] is True
            assert tx.state == WriteTransactionState.FINISHING


def test_publish_blocked_when_main_generation_changed(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    base_commit = "abc123"
    current_commit = "def456"
    tx._base_main_commit = base_commit

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = current_commit
        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
            assert "MAIN conflict" in result["reason"]


def test_main_conflict_independent_of_owner(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    base_commit = "abc123"
    current_commit = "def456"
    tx._base_main_commit = base_commit

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = current_commit
        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT


def test_version_not_advanced_on_main_conflict(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    base_commit = "abc123"
    current_commit = "def456"
    tx._base_main_commit = base_commit

    mock_version_manager = MagicMock()
    tx.set_version_manager(mock_version_manager)

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = current_commit
        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT

    mock_version_manager.create_pending_version.assert_not_called()


# === F1: Real Transaction Publish Conflict Test ===
def test_finish_editing_blocks_on_main_conflict(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)

    base_commit = "abc123"
    current_commit = "def456"

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = current_commit
        tx.start_editing(lambda: True)
        tx._base_main_commit = base_commit

        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            with patch.object(tx, '_create_pending_version', return_value=True):
                with patch.object(tx, '_publish_database_and_manifest', return_value=True):
                    with patch.object(tx, '_do_publish', return_value=False):
                        success = tx.finish_editing(
                            save_callback=lambda: True,
                            on_publish_success=lambda: None,
                            on_publish_failure=lambda e: None
                        )
            assert success is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
            mock_provider.publish_only.assert_not_called()
            mock_provider.publish.assert_not_called()


# === F2: publish_only() no fetch/pull ===
def test_publish_only_no_fetch_pull(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)
    tx._base_main_commit = "abc123"
    tx._pending_version = 99

    # Tạo mock sync service
    mock_sync = MagicMock()
    mock_sync.publish_only.return_value = True
    tx.set_sync_service(mock_sync)

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = "abc123"

        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            # Không mock _do_publish, để nó chạy thực tế và gọi sync_service.publish_only
            with patch.object(tx, '_create_pending_version', return_value=True):
                with patch.object(tx, '_publish_database_and_manifest', return_value=True):
                    tx.finish_editing(
                        save_callback=lambda: True,
                        on_publish_success=lambda: None,
                        on_publish_failure=lambda e: None
                    )
            # Kiểm tra sync_service.publish_only được gọi
            mock_sync.publish_only.assert_called_once()
            # provider.publish_only không được gọi (vì _do_publish gọi sync_service)
            mock_provider.publish_only.assert_not_called()


# === F3: MAIN Unavailable Block ===
def test_main_unavailable_blocks_publish(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.side_effect = Exception("Network error")
        tx.start_editing(lambda: True)
        tx._base_main_commit = None

        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
            assert "MAIN verification" in result["reason"].lower() or "unavailable" in result["reason"].lower()

            mock_provider.publish_only.assert_not_called()


# === Test race after validation ===
def test_push_rejected_after_validation(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)

    base_commit = "abc123"
    current_commit = "abc123"

    # Mock sync service để ném lỗi
    mock_sync = MagicMock()
    mock_sync.publish_only.side_effect = Exception("push rejected (non-fast-forward)")
    tx.set_sync_service(mock_sync)

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = current_commit
        tx.start_editing(lambda: True)
        tx._base_main_commit = base_commit

        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            tx._pending_version = 99

            with patch.object(tx, '_create_pending_version', return_value=True):
                with patch.object(tx, '_publish_database_and_manifest', return_value=True):
                    success = tx.finish_editing(
                        save_callback=lambda: True,
                        on_publish_success=lambda: None,
                        on_publish_failure=lambda e: None
                    )
            assert success is False
            assert tx.state == WriteTransactionState.OFFLINE_PENDING_PUBLISH
            # A push rejection is retained as a pending publication so the
            # already-prepared local commit can be retried without creating
            # another MAIN commit. No pull is allowed here.
            mock_provider.pull.assert_not_called()


# === Test base_main_commit None blocks publish ===
def test_base_main_commit_none_blocks_publish(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.return_value = "def456"
        tx.start_editing(lambda: True)
        tx._base_main_commit = None

        with patch.object(cm, 'validate_write_authority', return_value={
            "valid": True,
            "generation": 0,
            "owner": cm.get_session().session_id,
            "lease_valid": True,
            "finishing_deadline": None
        }):
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
            assert "unknown" in result["reason"].lower() or "unavailable" in result["reason"].lower()

def test_refresh_finishing_authority_main_failure(collab_manager):
    from datetime import datetime
    from datetime import datetime, timedelta
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)
    tx.enter_finishing()
    tx._base_main_commit = "abc123"

    current_gen = cm._lock.get_lock_generation()
    session_id = cm._session.session_id

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.remote_lock_status.return_value = {
            "locked": True,
            "session_id": session_id,
            "owner": cm._session.username,
            "username": cm._session.username,
            "last_heartbeat": datetime.now().isoformat(),
            "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
            "lock_generation": current_gen,
        }
        mock_provider.get_remote_main_commit.side_effect = Exception("Network error")

        with patch.object(cm, '_sync_local_lock', return_value=None):
            result = tx.refresh_finishing_authority()
            # Should be CONFLICT due to MAIN verification failure
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
            assert "main verification" in result["reason"].lower() or "unavailable" in result["reason"].lower()

def test_refresh_finishing_authority_main_unavailable_keeps_blocked(collab_manager):
    from centermanager.services.write_transaction import WriteTransactionState
    from datetime import datetime, timedelta

    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    # Giả lập trạng thái FINISHING_WAITING_FOR_COLLABORATION
    tx._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
    tx._finishing_started_at = datetime.now()
    tx._finishing_deadline = datetime.now() + timedelta(seconds=120)
    tx._expected_generation = cm._lock.get_lock_generation()
    tx._base_main_commit = "abc123"

    with patch.object(cm, 'validate_write_authority') as mock_auth:
        mock_auth.return_value = {"valid": True, "generation": 0, "owner": cm.get_session().session_id}

        with patch.object(cm, '_sync_provider') as mock_provider:
            # MAIN verification thất bại (exception)
            mock_provider.get_remote_main_commit.side_effect = Exception("Simulated MAIN fetch error")

            result = tx.refresh_finishing_authority()

            # Transaction vẫn bị chặn (non‑publishable)
            assert result["success"] is False
            assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
            assert "MAIN verification" in result["reason"] or "unavailable" in result["reason"].lower()

            # Đảm bảo không gọi publish
            mock_provider.publish_only.assert_not_called()
            mock_provider.publish.assert_not_called()