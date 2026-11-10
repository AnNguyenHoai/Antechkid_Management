"""Course-fee deployment and migration invariants. No production files touched."""
from sqlalchemy import create_engine, text

import pytest

from centermanager.platform.coursefee_deployment_guard import (
    CourseFeeDeploymentError, validate_coursefee_git_branch,
)
from centermanager.database.migration import assert_coursefee_database_lineage


@pytest.mark.parametrize("branch", ["main", "main_repos", "main_coursefee ", "", None, "lock-main_coursefee"])
def test_reject_non_coursefee_database_branch(branch):
    with pytest.raises(CourseFeeDeploymentError, match="main_coursefee"):
        validate_coursefee_git_branch(branch)


def test_explicit_coursefee_branch_is_allowed():
    validate_coursefee_git_branch("main_coursefee")


@pytest.mark.parametrize("table", [
    "monthly_tuition_plans", "monthly_tuition_allocations",
    "enrollment_monthly_tuition_terms", "monthly_tuition_outcomes",
    "monthly_class_defaults",
])
def test_wrong_product_schema_is_denied_before_migration(table):
    with create_engine("sqlite:///:memory:").begin() as connection:
        connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="Incompatible monthly-tuition database"):
            assert_coursefee_database_lineage(connection)


def test_colliding_old_revision_is_denied_before_migration():
    with create_engine("sqlite:///:memory:").begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('1e10a046')"))
        connection.execute(text("CREATE TABLE incomes (id INTEGER PRIMARY KEY, idempotency_key TEXT)"))
        with pytest.raises(RuntimeError, match="Ambiguous Alembic revision"):
            assert_coursefee_database_lineage(connection)


def test_legacy_baseline_and_distinct_coursefee_revision_are_allowed():
    for revision in ("1e10a045", "cf26a001"):
        with create_engine("sqlite:///:memory:").begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": revision})
            assert_coursefee_database_lineage(connection) is None


def test_bootstrap_checks_git_destination_before_provider_or_startup_sync():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / (
        "src/centermanager/platform/bootstrap/bootstrap_manager.py"
    )
    source = path.read_text(encoding="utf-8")
    guard = source.index("validate_coursefee_git_branch(git_config.branch)")
    provider = source.index("provider = GitSynchronizationProvider(")
    assert guard < provider
    assert "return False" in source[guard:provider]


def test_migration_refuses_wrong_product_before_ddl_and_stamping():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / (
        "src/centermanager/database/migration.py"
    )
    source = path.read_text(encoding="utf-8")
    upgrade = source[source.index("def _upgrade_database_with_engine("):]
    check = upgrade.index("assert_coursefee_database_lineage(connection)")
    assert check < upgrade.index('command.stamp(config, "5ce9314feb37")')
    assert check < upgrade.index('command.upgrade(config, "head")')


def test_coursefee_migration_tree_is_unambiguous():
    from pathlib import Path
    from alembic.script import ScriptDirectory
    from centermanager.database.migration import get_alembic_config
    path = Path(__file__).resolve().parents[1] / "migrations/versions"
    assert not (path / "1e10a046_coursefee_finance_submission_keys.py").exists()
    assert (path / "cf26a001_coursefee_finance_submission_keys.py").is_file()
    scripts = ScriptDirectory.from_config(get_alembic_config())
    assert scripts.get_current_head() == "cf26a001"
    assert scripts.get_revision("cf26a001").down_revision == "1e10a045"
