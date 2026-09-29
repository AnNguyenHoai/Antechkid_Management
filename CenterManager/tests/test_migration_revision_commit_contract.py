from pathlib import Path


def test_migration_uses_committing_transaction_for_alembic_revision():
    migration = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "centermanager"
        / "database"
        / "migration.py"
    ).read_text(encoding="utf-8")

    # SQLite DDL may survive a connection close while Alembic's
    # alembic_version DML is rolled back.  The migration lifecycle therefore
    # must own a committing transaction, not a bare engine.connect() context.
    assert "with engine.begin() as connection:" in migration

    upgrade_block = migration.split(
        "def _upgrade_database_with_engine", 1
    )[1].split("def upgrade_database_path_to_head", 1)[0]
    assert "with engine.connect() as connection:" not in upgrade_block
