import inspect
from types import SimpleNamespace

import pytest
from sqlalchemy import text

import centermanager.database.engine as db_engine
import centermanager.database.session as db_session
from centermanager.platform.backup.backup_service import BackupService


@pytest.fixture(autouse=True)
def _isolate_runtime_db_maintenance_fence():
    """Keep the process-global maintenance fence isolated between tests.

    Several restore/rollback tests intentionally monkeypatch refresh_runtime_db.
    Since quiesce_runtime_db now owns a real process-global fence, those older
    mocked refresh paths can otherwise leave maintenance enabled for a later
    test even though no production restore is still in progress.
    """
    db_engine.end_runtime_db_maintenance()
    try:
        yield
    finally:
        db_engine.end_runtime_db_maintenance()


def test_quiesce_fences_then_closes_sessions_and_all_runtime_engines(monkeypatch):
    events = []
    old_factory = SimpleNamespace()

    monkeypatch.setattr(db_session, "_session_factory", old_factory)
    monkeypatch.setattr(
        db_session,
        "begin_runtime_db_maintenance",
        lambda: events.append("begin_fence"),
    )
    monkeypatch.setattr(
        db_session,
        "close_all_sessions",
        lambda: events.append("close_all_sessions"),
    )
    monkeypatch.setattr(
        db_session,
        "dispose_runtime_engines",
        lambda: events.append("dispose_all_engines"),
    )

    db_session.quiesce_runtime_db()

    assert events == ["begin_fence", "close_all_sessions", "dispose_all_engines"]
    assert db_session._session_factory is None


def test_quiesce_releases_fence_if_sessions_cannot_close(monkeypatch):
    events = []
    old_factory = SimpleNamespace()

    monkeypatch.setattr(db_session, "_session_factory", old_factory)
    monkeypatch.setattr(
        db_session,
        "begin_runtime_db_maintenance",
        lambda: events.append("begin_fence"),
    )

    def _fail_close():
        events.append("close_all_sessions")
        raise RuntimeError("session close failed")

    monkeypatch.setattr(db_session, "close_all_sessions", _fail_close)
    monkeypatch.setattr(
        db_session,
        "end_runtime_db_maintenance",
        lambda: events.append("end_fence"),
    )

    with pytest.raises(RuntimeError, match="session close failed"):
        db_session.quiesce_runtime_db()

    assert events == ["begin_fence", "close_all_sessions", "end_fence"]
    assert db_session._session_factory is old_factory


def test_retained_runtime_engine_cannot_reopen_database_while_restore_fenced(tmp_path):
    """Regression for packaged WinError 32 after the first SEC06 handle fix.

    app.py owns an independent long-lived Engine/sessionmaker. Disposing an
    Engine does not make it unusable: without the maintenance fence that stale
    owner can immediately reconnect to center.db between quiesce and rename.
    """
    db_path = tmp_path / "center.db"
    engine = db_engine.create_engine_for_path(
        db_path,
        allow_create=True,
        runtime_guarded=True,
    )
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))

        db_engine.begin_runtime_db_maintenance()
        engine.dispose()

        with pytest.raises(db_engine.RuntimeDatabaseMaintenanceError):
            with engine.connect():
                pass

        db_engine.end_runtime_db_maintenance()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM probe")).scalar_one() == 0
    finally:
        engine.dispose()


def test_refresh_releases_fence_before_rebuilding_factory(monkeypatch):
    events = []
    new_factory = SimpleNamespace()

    monkeypatch.setattr(db_session, "runtime_db_maintenance_active", lambda: True)
    monkeypatch.setattr(
        db_session,
        "end_runtime_db_maintenance",
        lambda: events.append("end_fence"),
    )

    def _create():
        events.append("create")
        return new_factory

    monkeypatch.setattr(db_session, "create_session_factory", _create)
    monkeypatch.setattr(db_session, "_session_factory", SimpleNamespace())

    db_session.refresh_runtime_db()

    assert events == ["end_fence", "create"]
    assert db_session._session_factory is new_factory


def test_restore_keeps_maintenance_fence_across_live_database_rename():
    source = inspect.getsource(BackupService.restore_backup)

    quiesce_at = source.index("quiesce_runtime_db()")
    preserve_db_at = source.index("os.replace(runtime_db, old_db)")
    install_db_at = source.index("os.replace(db_tmp, runtime_db)")
    refresh_at = source.index("refresh_runtime_db()")

    assert quiesce_at < preserve_db_at < install_db_at < refresh_at
