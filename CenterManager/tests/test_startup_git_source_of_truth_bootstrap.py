# -*- coding: utf-8 -*-
"""Regression contract for authoritative Git database startup bootstrap."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "src" / "centermanager" / "platform" / "bootstrap" / "bootstrap_manager.py"
APP = ROOT / "src" / "centermanager" / "app.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_source(path: Path, class_name: str, method_name: str) -> str:
    source = _source(path)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    lines = source.splitlines()
                    return "\n".join(lines[child.lineno - 1 : child.end_lineno])
    raise AssertionError(f"{class_name}.{method_name} not found")


def test_bootstrap_materializes_git_database_before_runtime_ready():
    run_source = _method_source(BOOTSTRAP, "BootstrapManager", "run")

    sync_index = run_source.index("_ensure_authoritative_runtime_database(paths)")
    context_index = run_source.index("_build_runtime_context(paths)")
    ready_index = run_source.index("PlatformLifecycleState.READY")

    assert sync_index < context_index < ready_index
    assert "if not self._ensure_authoritative_runtime_database(paths):" in run_source
    assert "PlatformLifecycleState.STOPPED" in run_source


def test_missing_or_invalid_git_config_requires_first_run_dialog_then_sync():
    method = _method_source(
        BOOTSTRAP, "BootstrapManager", "_ensure_authoritative_runtime_database"
    )

    assert "GitConfigService" in method
    assert "GitConfigDialog" in method
    assert "git_config_service.has_config()" in method
    assert "dialog.exec()" in method
    assert "dialog.DialogCode.Accepted" in method
    assert "GitSynchronizationProvider" in method
    assert "StartupSynchronization(provider).run()" in method
    assert "DatabaseLifecycle(runtime_db).inspect()" in method
    assert "DatabaseLifecycleState.AVAILABLE" in method


def test_git_executable_and_sync_fail_closed_instead_of_offline_fallback():
    method = _method_source(
        BOOTSTRAP, "BootstrapManager", "_ensure_authoritative_runtime_database"
    )

    assert "if not git_executable:" in method
    assert "return False" in method
    assert "Authoritative Git synchronization failed" in method
    assert "local/offline mode" not in method


def test_default_runtime_creation_never_creates_an_empty_business_database():
    method = _method_source(BOOTSTRAP, "BootstrapManager", "_create_default_runtime")

    assert "paths.ensure_directories()" in method
    assert "RuntimeManifest" in method
    assert "center.db" not in method
    assert "initialize_runtime_database" not in method
    assert "sqlite" not in method.lower()


def test_app_runs_platform_bootstrap_before_legacy_database_initialization_call():
    """The remaining compatibility no-op cannot run before Git materialization."""
    source = _source(APP)

    bootstrap_index = source.index("bootstrap.run()")
    initialize_index = source.index("initialize_runtime_database()")
    engine_index = source.index("create_production_engine(echo=False)")
    schema_index = source.index("ensure_schema()")

    assert bootstrap_index < initialize_index < engine_index < schema_index
