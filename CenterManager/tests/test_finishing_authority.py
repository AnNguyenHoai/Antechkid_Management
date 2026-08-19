# -*- coding: utf-8 -*-
"""Tests for FINISHING authority fencing."""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from centermanager.platform.collaboration import CollaborationManager
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.events.event_bus import EventBus


@pytest.fixture
def collab_manager(tmp_path):
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")
    return cm


def test_enter_finishing_ok(collab_manager):
    """Test that entering FINISHING works when authority is valid."""
    cm = collab_manager
    cm.request_write()  # acquire lock

    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    result = tx.enter_finishing()
    assert result["success"] is True
    assert tx.state == WriteTransactionState.FINISHING
    assert tx._finishing_deadline is not None
    assert tx._finishing_started_at is not None
    assert tx._publish_intent is True

    # Check collaboration state
    auth = cm.validate_write_authority(cm.get_session())
    assert auth["valid"] is True
    assert auth["finishing_deadline"] is not None
    assert cm._lock.get_publish_intent() is True


def test_enter_finishing_stale_generation(collab_manager):
    """Test that entering FINISHING with stale generation fails."""
    cm1 = collab_manager
    cm1.request_write()
    tx1 = WriteTransactionManager(cm1)
    tx1.start_editing(lambda: True)

    # Simulate takeover by another instance
    cm2 = CollaborationManager(runtime_root=cm1._runtime_root, event_bus=EventBus())
    cm2.initialize("user2", "user2", "teacher")

    # Takeover: change owner and increment generation
    lock_data = cm1._lock._read_lock()
    lock_data["session_id"] = cm2._session.session_id
    cm1._lock._write_lock(lock_data)
    cm1._lock.increment_generation()  # B takes over

    result = tx1.enter_finishing()
    assert result["success"] is False
    assert tx1.state == WriteTransactionState.FINISHING_STALE
    # The reason should indicate owner mismatch or stale
    assert "Owner mismatch" in result["reason"] or "stale" in result["reason"].lower()


def test_generation_mismatch_independent_of_owner(collab_manager):
    """Test generation mismatch even when owner is same."""
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    # Keep owner same but increment generation
    cm._lock.increment_generation()

    result = tx.enter_finishing()
    assert result["success"] is False
    assert tx.state == WriteTransactionState.FINISHING_STALE
    assert "Generation mismatch" in result["reason"]


def test_finishing_deadline_absolute(collab_manager):
    """Test that deadline is absolute and cannot be extended by renewal."""
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)
    tx.enter_finishing()

    original_deadline = tx._finishing_deadline
    result = tx.refresh_finishing_authority()
    assert result["success"] is True
    # Deadline should not change
    assert tx._finishing_deadline == original_deadline


def test_collaboration_unavailable_blocks_publish(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    # Mock collaboration unavailable
    with patch.object(cm, 'is_collaboration_available', return_value=False):
        # Also need to ensure remote_lock_status returns a valid lock
        with patch.object(cm, '_sync_provider') as mock_provider:
            mock_provider.remote_lock_status.return_value = {
                "locked": True,
                "session_id": cm._session.session_id,
                "owner": cm._session.username,
                "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
                "lock_generation": 1,  # <-- ADDED
            }
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION


def test_collaboration_recovery_after_unavailable(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    # Simulate collaboration unavailable
    with patch.object(cm, 'is_collaboration_available', return_value=False):
        with patch.object(cm, '_sync_provider') as mock_provider:
            mock_provider.remote_lock_status.return_value = {
                "locked": True,
                "session_id": cm._session.session_id,
                "owner": cm._session.username,
                "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
                "lock_generation": 1,  # <-- ADDED
            }
            result = tx.enter_finishing()
            assert result["success"] is False
            assert tx.state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION

    # Now collaboration is available again, but lease still valid
    with patch.object(cm, 'is_collaboration_available', return_value=True):
        with patch.object(cm, '_sync_provider') as mock_provider:
            mock_provider.remote_lock_status.return_value = {
                "locked": True,
                "session_id": cm._session.session_id,
                "owner": cm._session.username,
                "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
                "lock_generation": 1,  # <-- ADDED
            }
            result = tx.refresh_finishing_authority()
            assert result["success"] is True
            assert tx.state == WriteTransactionState.FINISHING


def test_deadline_expiry_while_waiting(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    past = datetime.now() - timedelta(seconds=10)
    tx._finishing_deadline = past

    with patch.object(cm, 'is_collaboration_available', return_value=False):
        with patch.object(cm, '_sync_provider') as mock_provider:
            mock_provider.remote_lock_status.return_value = {
                "locked": True,
                "session_id": cm._session.session_id,
                "owner": cm._session.username,
                "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
                "lock_generation": 1,
            }
            tx.enter_finishing()
            assert tx.state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION

            result = tx.refresh_finishing_authority()
            assert result["success"] is False
            # Deadline expired → stale
            assert tx.state == WriteTransactionState.FINISHING_STALE
            assert "Deadline expired" in result["reason"]


def test_stale_session_cannot_publish(collab_manager):
    """Test that stale session cannot publish MAIN."""
    cm1 = collab_manager
    cm1.request_write()
    tx1 = WriteTransactionManager(cm1)
    tx1.start_editing(lambda: True)

    # Simulate takeover by another instance
    cm2 = CollaborationManager(runtime_root=cm1._runtime_root, event_bus=EventBus())
    cm2.initialize("user2", "user2", "teacher")

    # Takeover: change owner and increment generation
    lock_data = cm1._lock._read_lock()
    lock_data["session_id"] = cm2._session.session_id
    cm1._lock._write_lock(lock_data)
    cm1._lock.increment_generation()

    result = tx1.enter_finishing()
    assert result["success"] is False
    assert tx1.state == WriteTransactionState.FINISHING_STALE
    assert "Owner mismatch" in result["reason"] or "stale" in result["reason"].lower()


def test_heartbeat_timeout_during_finishing(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    # Create lock with valid lease and finishing deadline
    lock_data = cm._lock._read_lock()
    now = datetime.now()
    lock_data["lease_expires_at"] = (now + timedelta(seconds=60)).isoformat()
    lock_data["finishing_started_at"] = now.isoformat()
    lock_data["finishing_deadline"] = (now + timedelta(seconds=120)).isoformat()
    lock_data["publish_intent"] = True
    cm._lock._write_lock(lock_data)

    # Push to remote if in remote mode
    if cm._sync_provider is not None:
        expected_oid = cm._sync_provider._remote_lock_oid()
        commit_sha = cm._sync_provider._create_lock_commit_plumbing(lock_data, expected_oid)
        cm._sync_provider._push_lock_branch(commit_sha, expected_oid)
        cm._sync_local_lock()

    # Set stale heartbeat
    lock_data["last_heartbeat"] = (now - timedelta(seconds=70)).isoformat()
    cm._lock._write_lock(lock_data)

    auth = cm.validate_write_authority(cm.get_session())
    # In FINISHING, heartbeat stale is ignored → valid should be True
    assert auth["valid"] is True


def test_absolute_deadline_expiry(collab_manager):
    """Test that after deadline expires, session becomes stale."""
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)
    tx.enter_finishing()

    # Set deadline quá khứ
    past = datetime.now() - timedelta(seconds=10)
    cm._lock.set_finishing_data(past - timedelta(seconds=120), past, True)

    auth = cm.validate_write_authority(cm.get_session())
    assert auth["valid"] is False
    assert "deadline expired" in auth["reason"].lower()


def test_normal_editing_heartbeat_timeout(collab_manager):
    """Test that heartbeat timeout still applies in normal EDITING (local mode only)."""
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    # Không vào FINISHING, set heartbeat cũ
    lock_data = cm._lock._read_lock()
    old_hb = (datetime.now() - timedelta(seconds=70)).isoformat()
    lock_data["last_heartbeat"] = old_hb
    cm._lock._write_lock(lock_data)

    auth = cm.validate_write_authority(cm.get_session())
    # Nếu ở remote mode, lease vẫn hợp lệ nên valid=True
    # Nếu ở local mode, heartbeat stale nên valid=False
    # Test này được viết cho local mode, nhưng fixture collab_manager có thể ở remote mode
    # Chúng ta chỉ kiểm tra kết quả phù hợp với mode hiện tại
    if cm._sync_provider is not None:
        # Remote mode: lease still valid → valid should be True
        assert auth["valid"] is True
    else:
        # Local mode: heartbeat stale → valid should be False
        assert auth["valid"] is False
        assert "stale" in auth["reason"].lower() or "heartbeat" in auth["reason"].lower()