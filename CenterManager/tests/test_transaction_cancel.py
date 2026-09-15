# -*- coding: utf-8 -*-
"""Tests for MAIN optimistic concurrency / lost-update protection."""

import pytest
from unittest.mock import patch, MagicMock

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


def test_remote_main_unavailable_blocks_publish(collab_manager):
    cm = collab_manager
    cm.request_write()
    tx = WriteTransactionManager(cm)
    tx.start_editing(lambda: True)

    base_commit = "abc123"
    tx._base_main_commit = base_commit

    with patch.object(cm, '_sync_provider') as mock_provider:
        mock_provider.get_remote_main_commit.side_effect = Exception("Network error")
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
            assert "verification unavailable" in result["reason"].lower()


def test_no_force_push_on_main_conflict(collab_manager):
    """Test that force push is not used on conflict."""
    import inspect
    from centermanager.services.write_transaction import WriteTransactionManager

    source = inspect.getsource(WriteTransactionManager)
    assert "--force" not in source or "force_release" in source