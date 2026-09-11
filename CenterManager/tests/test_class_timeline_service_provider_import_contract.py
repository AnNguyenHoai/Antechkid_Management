"""Regression guard for ClassTimelineService provider-only dependency."""
from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "class_timeline_service.py"


def test_class_timeline_service_imports_repository_provider_only() -> None:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    repository_imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            repository_imports.extend(
                alias.name
                for alias in node.names
                if alias.name.startswith("centermanager.repositories")
                and alias.name != "centermanager.repositories.provider"
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("centermanager.repositories") and module != "centermanager.repositories.provider":
                repository_imports.append(module)

    assert repository_imports == []
