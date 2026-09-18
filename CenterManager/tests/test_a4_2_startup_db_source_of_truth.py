# -*- coding: utf-8 -*-
"""A4.2 startup database source-of-truth contract tests."""

from pathlib import Path

import centermanager.platform.sync.startup_sync as startup_sync_module
from centermanager.platform.sync.startup_sync import StartupSynchronization


class _FakePaths:
    def __init__(self, root: Path):
        self.runtime_root = root / "runtime"
        self.database_dir = self.runtime_root / "Database"
        self.metadata_dir = self.runtime_root / "metadata"
        self.database_dir.mkdir(parents=True)
        self.metadata_dir.mkdir(parents=True)


class _FakeProvider:
    def __init__(self):
        self.calls = []

    def connect(self):
        self.calls.append("connect")
        return True

    def fetch(self):
        self.calls.append("fetch")
        return True

    def reset_to_remote(self):
        self.calls.append("reset")
        return True

    def clone(self, progress_callback=None):
        self.calls.append("clone")
        return True


def _make_sync(tmp_path, monkeypatch):
    paths = _FakePaths(tmp_path)
    monkeypatch.setattr(startup_sync_module, "get_paths", lambda: paths)
    sync = StartupSynchronization(_FakeProvider())
    sync._refresh_database_sessions = lambda: None
    return sync, paths


def test_startup_sync_replaces_existing_runtime_database_from_repository(tmp_path, monkeypatch):
    sync, paths = _make_sync(tmp_path, monkeypatch)

    repo = paths.runtime_root / "repository"
    repo_db = repo / "database" / "center.db"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()
    repo_db.parent.mkdir(parents=True)
    repo_db.write_bytes(b"GIT-AUTHORITATIVE-DATABASE")

    paths.database_dir.joinpath("center.db").write_bytes(b"STALE-LOCAL-DATABASE")

    assert sync.run() is True
    assert paths.database_dir.joinpath("center.db").read_bytes() == repo_db.read_bytes()


def test_startup_sync_fails_when_authoritative_repository_database_is_missing(
    tmp_path, monkeypatch
):
    sync, paths = _make_sync(tmp_path, monkeypatch)

    repo = paths.runtime_root / "repository"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()
    paths.database_dir.joinpath("center.db").write_bytes(b"STALE-LOCAL-DATABASE")

    assert sync.run() is False
    assert paths.database_dir.joinpath("center.db").read_bytes() == b"STALE-LOCAL-DATABASE"


def test_app_materializes_git_database_before_creating_production_engine():
    source = (
        Path(__file__).resolve().parents[1] / "src/centermanager/app.py"
    ).read_text(encoding="utf-8")

    sync_marker = 'logger.info("[STARTUP] Running startup synchronization...")'
    engine_marker = "engine = create_production_engine(echo=False)"
    initialize_marker = "initialize_runtime_database()"

    assert source.index(sync_marker) < source.index(initialize_marker)
    assert source.index(initialize_marker) < source.index(engine_marker)
    assert source.index(engine_marker) < source.index("        # ENSURE DATABASE SCHEMA (after Git DB materialization)")


def test_app_refuses_configured_startup_sync_failure():
    source = (
        Path(__file__).resolve().parents[1] / "src/centermanager/app.py"
    ).read_text(encoding="utf-8")

    assert "refusing to start with a non-authoritative database" in source
    assert "return 1" in source[source.index("refusing to start"):source.index("refusing to start") + 500]


def test_startup_sync_contract_is_remote_database_source_of_truth():
    source = (
        Path(__file__).resolve().parents[1]
        / "src/centermanager/platform/sync/startup_sync.py"
    ).read_text(encoding="utf-8")

    assert 'repo_db = self._repo_path / "database" / "center.db"' in source
    assert "with open(repo_db, 'rb')" in source
    assert "with open(self._runtime_db_path, 'wb')" in source
    assert "return False" in source[source.index("if not repo_db.exists()"):source.index("if not repo_db.exists()") + 250]
