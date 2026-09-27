# -*- coding: utf-8 -*-
import sqlite3
import sys

import pytest

from centermanager.database.encryption import database_encryption_required
from centermanager.database.startup_security import (
    StartupDatabaseReadiness,
    inspect_authoritative_database_for_startup,
)
from centermanager.security.deployment_profile import (
    DeploymentProfile,
    DeploymentProfileError,
    deployment_profile,
)


def _clear_security_env(monkeypatch):
    monkeypatch.delenv("ANTECHKIDS_DEPLOYMENT_PROFILE", raising=False)
    monkeypatch.delenv("ANTECHKIDS_FORCE_DATABASE_ENCRYPTION", raising=False)


def test_source_execution_defaults_to_development(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert deployment_profile() is DeploymentProfile.DEVELOPMENT
    assert database_encryption_required() is False


def test_frozen_execution_defaults_to_production(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert deployment_profile() is DeploymentProfile.PRODUCTION
    assert database_encryption_required() is True


def test_explicit_production_override_requires_encryption(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("ANTECHKIDS_DEPLOYMENT_PROFILE", "production")

    assert deployment_profile() is DeploymentProfile.PRODUCTION
    assert database_encryption_required() is True


def test_force_encryption_still_supports_security_uat(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("ANTECHKIDS_FORCE_DATABASE_ENCRYPTION", "1")

    assert database_encryption_required() is True


def test_invalid_profile_fails_closed(monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("ANTECHKIDS_DEPLOYMENT_PROFILE", "prod-ish")

    with pytest.raises(DeploymentProfileError):
        deployment_profile()


def test_development_accepts_plaintext_authoritative_test_database(tmp_path, monkeypatch):
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("ANTECHKIDS_DEPLOYMENT_PROFILE", "development")
    db = tmp_path / "center.db"
    connection = sqlite3.connect(db)
    try:
        connection.execute("CREATE TABLE smoke (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    result = inspect_authoritative_database_for_startup(db)

    assert result.state is StartupDatabaseReadiness.READY
