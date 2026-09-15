"""Regression test for startup imports of Employee Workspace capabilities."""

import ast
from pathlib import Path


TARGET = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "ui"
    / "employee_workspace"
    / "employee_workspace_capabilities.py"
)


def test_employee_workspace_capabilities_has_valid_future_annotations_import():
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    future_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "__future__"
    ]

    assert any(
        alias.name == "annotations"
        for node in future_imports
        for alias in node.names
    )
