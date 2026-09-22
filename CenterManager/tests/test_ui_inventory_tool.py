# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "ui_inventory.py"
UI_ROOT = PROJECT_ROOT / "src" / "centermanager" / "ui"


def _load_tool():
    spec = importlib.util.spec_from_file_location("ui_inventory_tool", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _classes_by_name(inventory: dict) -> dict[str, dict]:
    return {item["name"]: item for item in inventory["classes"]}


def test_inventory_discovers_core_surfaces():
    tool = _load_tool()
    classes = _classes_by_name(tool.scan_ui(UI_ROOT))
    assert "MainWindow" in classes
    assert "HomePage" in classes
    assert "StudentWorkspaceShell" in classes
    assert "WorkspaceHeader" in classes
    assert "WorkspaceNavigation" in classes


def test_inventory_categories_are_stable_for_core_types():
    tool = _load_tool()
    classes = _classes_by_name(tool.scan_ui(UI_ROOT))
    assert classes["MainWindow"]["category"] == "screen"
    assert classes["HomePage"]["category"] == "screen"
    assert classes["StudentWorkspaceShell"]["category"] == "shell"
    assert classes["WorkspaceHeader"]["category"] == "component"
    assert classes["WorkspaceNavigation"]["category"] == "component"


def test_inventory_is_deterministic():
    tool = _load_tool()
    assert tool.scan_ui(UI_ROOT) == tool.scan_ui(UI_ROOT)
