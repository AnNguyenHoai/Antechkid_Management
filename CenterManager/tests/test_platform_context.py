# -*- coding: utf-8 -*-
"""Tests for PlatformContext and related components."""

import pytest
from datetime import datetime

from centermanager.platform.context import (
    PlatformContext,
    RuntimeContext,
    DeploymentContext,
    SessionContext,
    WorkspaceContext,
    UserContext,
    ConfigurationContext,
)
from centermanager.platform.lifecycle import PlatformLifecycle, PlatformLifecycleState
from centermanager.platform.runtime.context.runtime_state import RuntimeState, RuntimeStateMachine


class TestPlatformContext:
    def test_create_default(self):
        ctx = PlatformContext.create_default()
        assert ctx.runtime is not None
        assert ctx.deployment is not None
        assert ctx.session is not None
        assert ctx.workspace is not None
        assert ctx.user is not None
        assert ctx.configuration is not None

    def test_context_composition(self):
        ctx = PlatformContext.create_default()
        # Each context is independent
        ctx.session.mode = "WRITE"
        assert ctx.runtime is not ctx.session
        assert ctx.deployment is not ctx.workspace

    def test_runtime_state_transition(self):
        ctx = PlatformContext.create_default()
        ctx.runtime.state.transition_to(RuntimeState.READY)
        assert ctx.runtime.is_ready()

    def test_deployment_context(self):
        ctx = DeploymentContext(profile="collaborative")
        assert ctx.is_collaborative()
        assert not ctx.is_server()

    def test_session_context_heartbeat(self):
        ctx = SessionContext()
        ctx.started_at = datetime.now()
        ctx.last_heartbeat = datetime.now()
        assert ctx.is_active() is True

    def test_user_context_permission(self):
        ctx = UserContext()
        ctx.is_admin = True
        assert ctx.has_permission("any") is True

    def test_workspace_context_set_active(self):
        ctx = WorkspaceContext()
        ctx.set_active("test_ws", "Test Workspace", "page1")
        assert ctx.active_workspace_id == "test_ws"
        assert len(ctx.navigation_history) == 1


class TestPlatformLifecycle:
    def test_initial_state(self):
        lifecycle = PlatformLifecycle()
        assert lifecycle.state == PlatformLifecycleState.CREATED

    def test_transition_to_ready(self):
        lifecycle = PlatformLifecycle()
        lifecycle.transition_to(PlatformLifecycleState.READY)
        assert lifecycle.state == PlatformLifecycleState.READY
        assert lifecycle.previous_state == PlatformLifecycleState.CREATED

    def test_transition_to_running(self):
        lifecycle = PlatformLifecycle()
        lifecycle.transition_to(PlatformLifecycleState.RUNNING)
        assert lifecycle.started_at is not None

    def test_is_ready(self):
        lifecycle = PlatformLifecycle()
        assert not lifecycle.is_ready()
        lifecycle.transition_to(PlatformLifecycleState.READY)
        assert lifecycle.is_ready()

    def test_is_stopped(self):
        lifecycle = PlatformLifecycle()
        lifecycle.transition_to(PlatformLifecycleState.STOPPED)
        assert lifecycle.is_stopped()
        assert lifecycle.stopped_at is not None