# -*- coding: utf-8 -*-
"""Regression coverage for SEC06 Windows restore DB-handle quiescence."""

import sqlite3

import pytest

from centermanager.database import engine as engine_module


def _create_lifecycle_valid_database(db_path):
    """Create the smallest SQLite DB accepted by DatabaseLifecycle."""
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "CREATE TABLE sec06_probe (id INTEGER PRIMARY KEY)"
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def reset_runtime_handle_registry():
    engine_module.end_runtime_db_maintenance()
    engine_module.close_runtime_dbapi_connections()
    yield
    engine_module.end_runtime_db_maintenance()
    engine_module.close_runtime_dbapi_connections()


def test_guarded_engine_tracks_checked_out_dbapi_connection(tmp_path):
    db_path = tmp_path / "center.db"
    _create_lifecycle_valid_database(db_path)
    engine = engine_module.create_engine_for_path(
        db_path, allow_create=False, runtime_guarded=True
    )

    connection = engine.connect()
    assert engine_module.runtime_dbapi_connection_count() == 1

    connection.close()
    assert engine_module.runtime_dbapi_connection_count() == 0


def test_drain_force_closes_checked_out_connection_and_reaches_zero(tmp_path):
    db_path = tmp_path / "center.db"
    _create_lifecycle_valid_database(db_path)
    engine = engine_module.create_engine_for_path(
        db_path, allow_create=False, runtime_guarded=True
    )
    connection = engine.connect()
    raw = connection.connection.driver_connection

    engine_module.begin_runtime_db_maintenance()
    engine.dispose()
    # NullPool/Engine.dispose is not the invariant: the checked-out handle is
    # still tracked until the explicit recovery drain closes it.
    assert engine_module.runtime_dbapi_connection_count() == 1

    engine_module.close_runtime_dbapi_connections()
    assert engine_module.runtime_dbapi_connection_count() == 0
    with pytest.raises(sqlite3.ProgrammingError):
        raw.execute("SELECT 1")


def test_maintenance_fence_prevents_reacquiring_handle(tmp_path):
    db_path = tmp_path / "center.db"
    _create_lifecycle_valid_database(db_path)
    engine = engine_module.create_engine_for_path(
        db_path, allow_create=False, runtime_guarded=True
    )

    engine_module.begin_runtime_db_maintenance()
    with pytest.raises(engine_module.RuntimeDatabaseMaintenanceError):
        engine.connect()
    assert engine_module.runtime_dbapi_connection_count() == 0
