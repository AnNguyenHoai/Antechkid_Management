import pytest

from centermanager.database import engine as database_engine


class _CloseFailureConnection:
    def close(self):
        raise OSError("simulated Windows handle close failure")


class _ClosableConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _isolated_runtime_db_registry():
    with database_engine._runtime_db_gate:
        original = dict(database_engine._runtime_dbapi_connections)
        database_engine._runtime_dbapi_connections.clear()
    try:
        yield
    finally:
        with database_engine._runtime_db_gate:
            database_engine._runtime_dbapi_connections.clear()
            database_engine._runtime_dbapi_connections.update(original)


def test_failed_close_remains_registered_and_fails_closed():
    """A failed native close must never be reported as zero runtime DB handles."""
    connection = _CloseFailureConnection()
    database_engine._register_runtime_dbapi_connection(connection)

    with pytest.raises(database_engine.RuntimeDatabaseMaintenanceError) as exc_info:
        database_engine.close_runtime_dbapi_connections()

    assert database_engine.runtime_dbapi_connection_count() == 1
    assert id(connection) in database_engine._runtime_dbapi_connections
    assert "1 handle(s) remain registered" in str(exc_info.value)


def test_successful_close_is_removed_from_registry():
    connection = _ClosableConnection()
    database_engine._register_runtime_dbapi_connection(connection)

    database_engine.close_runtime_dbapi_connections()

    assert connection.closed is True
    assert database_engine.runtime_dbapi_connection_count() == 0


def test_mixed_close_results_preserve_only_failed_handle():
    successful = _ClosableConnection()
    failed = _CloseFailureConnection()
    database_engine._register_runtime_dbapi_connection(successful)
    database_engine._register_runtime_dbapi_connection(failed)

    with pytest.raises(database_engine.RuntimeDatabaseMaintenanceError):
        database_engine.close_runtime_dbapi_connections()

    assert successful.closed is True
    assert id(successful) not in database_engine._runtime_dbapi_connections
    assert id(failed) in database_engine._runtime_dbapi_connections
    assert database_engine.runtime_dbapi_connection_count() == 1
