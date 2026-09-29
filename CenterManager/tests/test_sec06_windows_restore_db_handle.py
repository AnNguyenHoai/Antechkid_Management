import inspect
from types import SimpleNamespace

import pytest

import centermanager.database.session as db_session
from centermanager.platform.backup.backup_service import BackupService


class _Engine:
    def __init__(self, events):
        self.events = events

    def dispose(self):
        self.events.append("dispose")


class _Factory:
    def __init__(self, engine):
        self.kw = {"bind": engine}


def test_quiesce_closes_sessions_before_disposing_engine(monkeypatch):
    events = []
    engine = _Engine(events)
    factory = _Factory(engine)

    monkeypatch.setattr(db_session, "_session_factory", factory)
    monkeypatch.setattr(
        db_session,
        "close_all_sessions",
        lambda: events.append("close_all_sessions"),
    )

    db_session.quiesce_runtime_db()

    assert events == ["close_all_sessions", "dispose"]
    assert db_session._session_factory is None


def test_quiesce_fails_closed_before_dispose_when_sessions_cannot_close(monkeypatch):
    events = []
    engine = _Engine(events)
    factory = _Factory(engine)

    monkeypatch.setattr(db_session, "_session_factory", factory)

    def _fail_close():
        events.append("close_all_sessions")
        raise RuntimeError("session close failed")

    monkeypatch.setattr(db_session, "close_all_sessions", _fail_close)

    with pytest.raises(RuntimeError, match="session close failed"):
        db_session.quiesce_runtime_db()

    # No destructive restore should continue after a failed process-wide close.
    assert events == ["close_all_sessions"]
    assert db_session._session_factory is factory


def test_refresh_rebuilds_factory_only_after_quiesce(monkeypatch):
    events = []
    new_factory = SimpleNamespace()

    monkeypatch.setattr(
        db_session,
        "quiesce_runtime_db",
        lambda: events.append("quiesce"),
    )

    def _create():
        events.append("create")
        return new_factory

    monkeypatch.setattr(db_session, "create_session_factory", _create)
    monkeypatch.setattr(db_session, "_session_factory", SimpleNamespace())

    db_session.refresh_runtime_db()

    assert events == ["quiesce", "create"]
    assert db_session._session_factory is new_factory


def test_restore_quiesces_before_first_live_database_rename():
    source = inspect.getsource(BackupService.restore_backup)

    quiesce_at = source.index("quiesce_runtime_db()")
    preserve_db_at = source.index("os.replace(runtime_db, old_db)")
    install_db_at = source.index("os.replace(db_tmp, runtime_db)")
    refresh_at = source.index("refresh_runtime_db()")

    assert quiesce_at < preserve_db_at < install_db_at < refresh_at
