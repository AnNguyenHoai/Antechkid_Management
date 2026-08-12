# -*- coding: utf-8 -*-
"""Tests for RuntimeContext and related components."""

import pytest
from datetime import datetime
import uuid

from centermanager.platform.runtime.context import (
    RuntimeContext,
    RuntimeManifest,
    RuntimeState,
    RuntimeStateMachine,
    RuntimeConfiguration,
    RuntimeSession,
    RuntimeVersion,
)


class TestRuntimeState:
    def test_initial_state(self):
        sm = RuntimeStateMachine()
        assert sm.current == RuntimeState.BOOTSTRAP
        assert sm.previous is None

    def test_transition(self):
        sm = RuntimeStateMachine()
        sm.transition_to(RuntimeState.INITIALIZING)
        assert sm.current == RuntimeState.INITIALIZING
        assert sm.previous == RuntimeState.BOOTSTRAP

    def test_is_ready(self):
        sm = RuntimeStateMachine()
        assert not sm.is_ready()
        sm.transition_to(RuntimeState.READY)
        assert sm.is_ready()

    def test_is_error(self):
        sm = RuntimeStateMachine()
        assert not sm.is_error()
        sm.transition_to(RuntimeState.ERROR)
        assert sm.is_error()


class TestRuntimeManifest:
    def test_default(self):
        manifest = RuntimeManifest()
        assert manifest.schema_version == 1
        assert manifest.runtime_version == 0
        assert manifest.publisher == "CenterManager"

    def test_get_version(self):
        manifest = RuntimeManifest(runtime_version=5)
        assert manifest.get_version() == 5

    def test_to_dict(self):
        manifest = RuntimeManifest(runtime_version=3, branch="develop")
        data = manifest.to_dict()
        assert data["runtime_version"] == 3
        assert data["branch"] == "develop"
        assert "created_at" in data

    def test_from_dict(self):
        data = {
            "schema_version": 1,
            "runtime_version": 42,
            "database_version": 5,
            "minimum_app_version": "1.0.0",
            "publisher": "Test",
            "branch": "test-branch",
            "created_at": "2026-08-10T10:00:00",
            "published_at": "2026-08-10T12:00:00",
        }
        manifest = RuntimeManifest.from_dict(data)
        assert manifest.runtime_version == 42
        assert manifest.branch == "test-branch"
        assert manifest.publisher == "Test"


class TestRuntimeConfiguration:
    def test_default(self):
        config = RuntimeConfiguration()
        assert config.deployment_profile == "standalone"
        assert config.app_version == "0.1.0"

    def test_from_app_config(self):
        app_config = {
            "application": {"name": "TestApp", "version": "1.2.3"},
            "deployment": {"profile": "collaborative"},
            "collaboration": {"heartbeat_interval": 30, "lock_timeout": 120},
        }
        config = RuntimeConfiguration.from_app_config(app_config)
        assert config.deployment_profile == "collaborative"
        assert config.app_version == "1.2.3"
        assert config.heartbeat_interval == 30
        assert config.lock_timeout == 120


class TestRuntimeSession:
    def test_creation(self):
        session = RuntimeSession(
            session_id="sess-001",
            user_id="user-001",
            username="testuser",
            role="admin",
            machine_id="machine-001",
        )
        assert session.session_id == "sess-001"
        assert session.username == "testuser"
        assert session.mode == "READ"

    def test_heartbeat(self):
        session = RuntimeSession(
            session_id="sess-001",
            user_id="user-001",
            username="testuser",
            role="admin",
            machine_id="machine-001",
        )
        old_time = session.last_heartbeat
        session.update_heartbeat()
        assert session.last_heartbeat > old_time

    def test_is_active(self):
        session = RuntimeSession(
            session_id="sess-001",
            user_id="user-001",
            username="testuser",
            role="admin",
            machine_id="machine-001",
        )
        # Just created, should be active
        assert session.is_active(timeout_seconds=120)


class TestRuntimeVersion:
    def test_default(self):
        version = RuntimeVersion()
        assert version.current == 0
        assert version.desired is None

    def test_is_outdated(self):
        version = RuntimeVersion(current=5, desired=10)
        assert version.is_outdated() is True
        version.desired = 5
        assert version.is_outdated() is False

    def test_update_current(self):
        version = RuntimeVersion(current=5)
        version.update_current(6)
        assert version.current == 6
        assert version.last_pull is not None

    def test_mark_published(self):
        version = RuntimeVersion()
        version.mark_published(10)
        assert version.current == 10
        assert version.desired == 10
        assert version.last_publish is not None


class TestRuntimeContext:
    def test_creation(self):
        context = RuntimeContext(context_id="ctx-001")
        assert context.context_id == "ctx-001"
        assert context.created_at is not None
        assert context.state.current == RuntimeState.BOOTSTRAP

    def test_is_ready(self):
        context = RuntimeContext(context_id="ctx-001")
        assert not context.is_ready()
        context.state.transition_to(RuntimeState.READY)
        assert context.is_ready()

    def test_can_write_no_session(self):
        context = RuntimeContext(context_id="ctx-001")
        assert context.can_write() is False

    def test_can_write_with_session(self):
        context = RuntimeContext(context_id="ctx-001")
        session = RuntimeSession(
            session_id="sess-001",
            user_id="user-001",
            username="test",
            role="admin",
            machine_id="m1",
            mode="WRITE"
        )
        context.session = session
        assert context.can_write() is True

    def test_get_runtime_version(self):
        context = RuntimeContext(context_id="ctx-001")
        context.manifest.runtime_version = 5
        assert context.get_runtime_version() == 5