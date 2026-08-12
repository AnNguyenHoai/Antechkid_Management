# -*- coding: utf-8 -*-
"""Tests for WorkspaceRegistry."""

import pytest
from centermanager.platform.workspace import WorkspaceDescriptor, WorkspaceRegistry


def test_registry_register():
    registry = WorkspaceRegistry()
    desc = WorkspaceDescriptor(
        workspace_id="test",
        name="Test",
        icon="🧪",
        description="Test workspace",
        factory=lambda: "workspace"
    )
    registry.register(desc)
    assert registry.get_descriptor("test") is desc


def test_registry_list_descriptors():
    registry = WorkspaceRegistry()
    desc1 = WorkspaceDescriptor("ws1", "WS1", "📦", "Desc1", factory=lambda: None, order=2)
    desc2 = WorkspaceDescriptor("ws2", "WS2", "📦", "Desc2", factory=lambda: None, order=1)
    registry.register(desc1)
    registry.register(desc2)
    descriptors = registry.list_descriptors()
    assert descriptors[0].workspace_id == "ws2"
    assert descriptors[1].workspace_id == "ws1"


def test_registry_create_workspace():
    registry = WorkspaceRegistry()
    desc = WorkspaceDescriptor(
        workspace_id="test",
        name="Test",
        icon="🧪",
        description="Test workspace",
        factory=lambda: "instance"
    )
    registry.register(desc)
    instance = registry.create_workspace("test")
    assert instance == "instance"
    assert registry.get_workspace("test") == "instance"


def test_registry_create_unknown():
    registry = WorkspaceRegistry()
    instance = registry.create_workspace("unknown")
    assert instance is None