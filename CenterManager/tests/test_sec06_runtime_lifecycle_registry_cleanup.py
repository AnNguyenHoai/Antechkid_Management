import pytest

from centermanager.database import engine as database_engine


@pytest.fixture(autouse=True)
def isolate_runtime_db_registry():
    """Keep SEC06 lifecycle tests independent of the process-global registry."""
    with database_engine._runtime_db_gate:
        original = dict(database_engine._runtime_dbapi_connections)
        database_engine._runtime_dbapi_connections.clear()
    try:
        yield
    finally:
        with database_engine._runtime_db_gate:
            database_engine._runtime_dbapi_connections.clear()
            database_engine._runtime_dbapi_connections.update(original)
