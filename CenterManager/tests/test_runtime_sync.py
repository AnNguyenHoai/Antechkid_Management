# -*- coding: utf-8 -*-
"""Tests for Runtime Auto Synchronization."""

import pytest
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from centermanager.platform.sync import (
    RuntimeSyncService,
    SyncStatus,
    AutoPullPolicy,
    ReloadDecisionService,
    ReloadDecision,
    ReloadState,
)
from centermanager.platform.synchronization import (
    VersionResolver,
    VersionStatus,
    RetryPolicy,
    SynchronizationResult,
    SyncResult,
)
from centermanager.events.event_bus import EventBus


class TestAutoPullPolicy:
    def test_should_pull_all_conditions_met(self):
        policy = AutoPullPolicy()
        should, reason = policy.should_pull(
            is_ready=True,
            has_writer=False,
            queue_length=0,
            is_healthy=True,
            version_status=VersionStatus.OUTDATED,
        )
        assert should is True
        assert "All conditions met" in reason

    def test_should_pull_not_ready(self):
        policy = AutoPullPolicy()
        should, reason = policy.should_pull(
            is_ready=False,
            has_writer=False,
            queue_length=0,
            is_healthy=True,
            version_status=VersionStatus.OUTDATED,
        )
        assert should is False
        assert "not ready" in reason

    def test_should_pull_has_writer(self):
        policy = AutoPullPolicy()
        should, reason = policy.should_pull(
            is_ready=True,
            has_writer=True,
            queue_length=0,
            is_healthy=True,
            version_status=VersionStatus.OUTDATED,
        )
        assert should is False
        assert "Writer active" in reason

    def test_should_pull_queue_not_empty(self):
        policy = AutoPullPolicy()
        should, reason = policy.should_pull(
            is_ready=True,
            has_writer=False,
            queue_length=5,
            is_healthy=True,
            version_status=VersionStatus.OUTDATED,
        )
        assert should is False
        assert "queue" in reason

    def test_should_pull_up_to_date(self):
        policy = AutoPullPolicy()
        should, reason = policy.should_pull(
            is_ready=True,
            has_writer=False,
            queue_length=0,
            is_healthy=True,
            version_status=VersionStatus.UP_TO_DATE,
        )
        assert should is False


class TestReloadDecisionService:
    def test_reload_now(self):
        service = ReloadDecisionService()
        state = ReloadState()
        decision = service.decide(state)
        assert decision == ReloadDecision.RELOAD_NOW

    def test_wait_unsaved_changes(self):
        service = ReloadDecisionService()
        state = ReloadState(has_unsaved_changes=True)
        decision = service.decide(state)
        assert decision == ReloadDecision.WAIT

    def test_wait_is_writing(self):
        service = ReloadDecisionService()
        state = ReloadState(is_writing=True)
        decision = service.decide(state)
        assert decision == ReloadDecision.WAIT

    def test_wait_open_dialog(self):
        service = ReloadDecisionService()
        state = ReloadState(has_open_dialog=True)
        decision = service.decide(state)
        assert decision == ReloadDecision.WAIT

    def test_is_safe(self):
        service = ReloadDecisionService()
        state = ReloadState()
        assert service.is_safe(state) is True

        state = ReloadState(has_unsaved_changes=True)
        assert service.is_safe(state) is False


class TestRuntimeSyncService:
    @pytest.fixture
    def mock_sync_manager(self):
        manager = Mock()
        manager.check_updates.return_value = SynchronizationResult(
            result=SyncResult.NO_CHANGE,
            current_version=1,
            remote_version=1,
        )
        manager.begin_sync.return_value = SynchronizationResult(
            result=SyncResult.SUCCESS,
            current_version=1,
            remote_version=2,
        )
        return manager

    @pytest.fixture
    def mock_collab_manager(self):
        manager = Mock()
        session = Mock()
        session.session_id = "test-session"
        manager.get_session.return_value = session
        manager.is_writing.return_value = False
        manager.get_queue.return_value = {"requests": []}
        return manager

    @pytest.fixture
    def mock_context_manager(self):
        manager = Mock()
        context = Mock()
        context.is_ready.return_value = True
        manager.get_context.return_value = context
        return manager

    @pytest.fixture
    def mock_sync_provider(self):
        provider = Mock()
        provider.health.return_value = True
        return provider

    def test_initialization(self, mock_sync_manager, mock_collab_manager, mock_context_manager):
        service = RuntimeSyncService(
            sync_manager=mock_sync_manager,
            collab_manager=mock_collab_manager,
            context_manager=mock_context_manager,
            poll_interval=1,
        )
        assert service.current_state()["status"] == "idle"

    def test_check_updates(self, mock_sync_manager, mock_collab_manager, mock_context_manager):
        service = RuntimeSyncService(
            sync_manager=mock_sync_manager,
            collab_manager=mock_collab_manager,
            context_manager=mock_context_manager,
            poll_interval=1,
        )
        result = service.check_for_updates()
        mock_sync_manager.check_updates.assert_called_once()

    def test_start_stop(self, mock_sync_manager, mock_collab_manager, mock_context_manager):
        service = RuntimeSyncService(
            sync_manager=mock_sync_manager,
            collab_manager=mock_collab_manager,
            context_manager=mock_context_manager,
            poll_interval=1,
        )
        service.start()
        assert service._running is True
        time.sleep(0.1)
        service.stop()
        assert service._running is False

    def test_cancel_sync(self, mock_sync_manager, mock_collab_manager, mock_context_manager):
        service = RuntimeSyncService(
            sync_manager=mock_sync_manager,
            collab_manager=mock_collab_manager,
            context_manager=mock_context_manager,
            poll_interval=1,
        )
        service._set_status(SyncStatus.SYNCHRONIZING)
        result = service.cancel_sync()
        mock_sync_manager.cancel.assert_called_once()
        assert result is True

    def test_execute_sync(self, mock_sync_manager, mock_collab_manager, mock_context_manager):
        service = RuntimeSyncService(
            sync_manager=mock_sync_manager,
            collab_manager=mock_collab_manager,
            context_manager=mock_context_manager,
            poll_interval=1,
        )
        service._pending_update = True
        service._remote_version = 2

        result = service.execute_sync()
        mock_sync_manager.begin_sync.assert_called_once()
        assert result is True