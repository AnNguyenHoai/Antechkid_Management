"""BOOT-LEGACY-01: upgrade must reach verified Git recovery, never reset local by bootstrap.

These tests use mocked collaboration/UI context and disposable paths only.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.bootstrap import bootstrap_manager
from centermanager.platform.write_recovery import RecoveryRequired


def _bootstrap(monkeypatch, tmp_path, *, journal_error=None):
    paths = SimpleNamespace(
        runtime_root=tmp_path / "runtime",
        database_dir=tmp_path / "runtime" / "Database",
        metadata_dir=tmp_path / "runtime" / "metadata",
    )
    paths.runtime_root.mkdir()
    events = []

    class FakeJournal:
        def __init__(self, passed_paths):
            assert passed_paths is paths
        def inspect(self):
            events.append("metadata-inspected")
            if journal_error is not None:
                raise journal_error
            return None  # Legacy EXE workspace has no E1B journal receipt.

    monkeypatch.setattr(
        "centermanager.platform.write_recovery.WriteRecoveryJournal",
        FakeJournal,
    )
    monkeypatch.setattr(bootstrap_manager, "get_paths", lambda: paths)
    monkeypatch.setattr(
        bootstrap_manager, "get_config",
        lambda: SimpleNamespace(raw={}),
    )
    monkeypatch.setattr(
        bootstrap_manager, "load_config",
        lambda _: {},
    )
    manager = bootstrap_manager.BootstrapManager.__new__(
        bootstrap_manager.BootstrapManager
    )
    manager._lifecycle = SimpleNamespace(transition_to=lambda state: events.append("lifecycle"))
    manager._repo_manager = SimpleNamespace(
        detect=lambda: bootstrap_manager.RepositoryState.VALID,
        refresh=lambda: None,
        validate=lambda: True,
    )
    manager._context_manager = SimpleNamespace(install_context=lambda _: None)
    manager._build_runtime_context = lambda _: SimpleNamespace(
        state=SimpleNamespace(transition_to=lambda state: None)
    )
    manager._build_deployment_context = lambda _: SimpleNamespace()
    manager._ensure_authoritative_runtime_database = lambda _: (
        events.append("authoritative-sync") or True
    )
    # Context constructors have irrelevant dependencies here.
    monkeypatch.setattr(
        bootstrap_manager,
        "ConfigurationContext",
        SimpleNamespace(from_app_config=lambda _: SimpleNamespace()),
    )
    for symbol in ("SessionContext", "WorkspaceContext", "UserContext"):
        monkeypatch.setattr(bootstrap_manager, symbol, lambda: SimpleNamespace())
    monkeypatch.setattr(
        bootstrap_manager, "PlatformContext",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    return manager, events, paths


def test_legacy_missing_receipt_reaches_authoritative_sync(monkeypatch, tmp_path):
    manager, events, _ = _bootstrap(monkeypatch, tmp_path)
    assert manager.run() is True
    assert events.index("metadata-inspected") < events.index("authoritative-sync")
    # Git-authoritative sync owns the actual revalidation and preservation.
    assert "authoritative-sync" in events


def test_corrupt_journal_blocks_before_authoritative_sync(monkeypatch, tmp_path):
    manager, events, _ = _bootstrap(
        monkeypatch, tmp_path,
        journal_error=RecoveryRequired("Unreadable recovery journal"),
    )
    class MessageBox:
        @staticmethod
        def critical(*args):
            pass
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox", MessageBox)
    assert manager.run() is False
    assert "authoritative-sync" not in events


def test_default_runtime_does_not_overwrite_existing_legacy_manifest(
    monkeypatch, tmp_path,
):
    manager, _, paths = _bootstrap(monkeypatch, tmp_path)
    manifest = paths.runtime_root / "manifest.json"
    manifest.write_text('{"legacy":true}', encoding="utf-8")
    paths.ensure_directories = lambda: None
    manager._create_default_runtime(paths)
    assert manifest.read_text(encoding="utf-8") == '{"legacy":true}'
