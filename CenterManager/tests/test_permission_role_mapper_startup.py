# -*- coding: utf-8 -*-
"""Regression coverage for the Role <-> Permission ORM mapper contract."""

from sqlalchemy.orm import configure_mappers

from centermanager.models.permission import Permission
from centermanager.models.role import Role


def test_role_permission_mappers_configure_without_startup_error():
    """Importing the auth models must configure both sides of the relationship."""
    configure_mappers()

    assert "permissions" in Role.__mapper__.relationships
    assert "roles" in Permission.__mapper__.relationships

    assert Role.__mapper__.relationships["permissions"].back_populates == "roles"
    assert Permission.__mapper__.relationships["roles"].back_populates == "permissions"
