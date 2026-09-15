# -*- coding: utf-8 -*-
"""Regression tests for the public FINISHING authority contract."""

from datetime import datetime, timedelta

import pytest

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.services.write_transaction import WriteTransactionManager


@pytest.fixture
def collab_manager(tmp_path):
    manager = CollaborationManager(runtime_root=tmp_path, event_bus=EventBus())
    manager.initialize("test_user", "test_user", "admin")
    yield manager
    manager.shutdown()


def _start_editing(manager):
    assert manager.request_write().is_granted
    transaction = WriteTransactionManager(manager)
    assert transaction.start_editing(lambda: True)
    return transaction


def test_authority_exposes_active_finishing_deadline(collab_manager):
    transaction = _start_editing(collab_manager)

    result = transaction.enter_finishing()
    assert result["success"] is True

    authority = collab_manager.validate_write_authority(collab_manager.get_session())
    assert authority["valid"] is True
    assert authority["finishing_deadline"] == transaction._finishing_deadline

    transaction.cancel_editing(force=True)


def test_expired_finishing_deadline_has_precedence_over_heartbeat(collab_manager):
    transaction = _start_editing(collab_manager)
    assert transaction.enter_finishing()["success"] is True

    past = datetime.now() - timedelta(seconds=10)
    collab_manager._lock.set_finishing_data(
        past - timedelta(seconds=120),
        past,
        True,
    )

    authority = collab_manager.validate_write_authority(collab_manager.get_session())
    assert authority["valid"] is False
    assert authority["finishing_deadline"] == past
    assert "deadline expired" in authority["reason"].lower()


def test_editing_heartbeat_timeout_has_specific_reason(collab_manager):
    transaction = _start_editing(collab_manager)

    lock_data = collab_manager._lock._read_lock()
    lock_data["last_heartbeat"] = (
        datetime.now() - timedelta(seconds=70)
    ).isoformat()
    collab_manager._lock._write_lock(lock_data)

    authority = collab_manager.validate_write_authority(collab_manager.get_session())
    assert authority["valid"] is False
    assert "heartbeat timeout" in authority["reason"].lower()

    transaction.cancel_editing(force=True)
