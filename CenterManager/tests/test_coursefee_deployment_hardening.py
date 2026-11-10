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
