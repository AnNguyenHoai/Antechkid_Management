# -*- coding: utf-8 -*-
import pytest

from centermanager.platform.protected_data_service.domain_gateway import (
    ProtectedDomainAuthenticationError,
    ServiceSessionRegistry,
)
from centermanager.platform.protected_data_service.permission_adapter import (
    ProtectedPermissionServiceAdapter,
)
from centermanager.services.permission_service import AuthenticationError


def test_service_session_token_is_bound_to_windows_sid():
    registry = ServiceSessionRegistry(ttl_seconds=60)
    issued = registry.issue(7, "S-1-5-21-A")

    assert registry.require(issued.token, "S-1-5-21-A").user_id == 7
    with pytest.raises(ProtectedDomainAuthenticationError, match="invalid or expired"):
        registry.require(issued.token, "S-1-5-21-B")


def test_service_session_logout_revokes_token():
    registry = ServiceSessionRegistry(ttl_seconds=60)
    issued = registry.issue(9, "S-1-5-21-A")
    registry.revoke(issued.token, "S-1-5-21-A")
    with pytest.raises(ProtectedDomainAuthenticationError):
        registry.require(issued.token, "S-1-5-21-A")


class _Client:
    def __init__(self):
        self.changed = []
        self.logged_out = False

    def authenticate(self, username, password):
        assert password == "secret"
        return {
            "user_id": 42,
            "username": username,
            "full_name": "Employee Test",
            "role": "reception",
            "permissions": ["student.read", "student.create"],
            "force_password_change": True,
        }

    def change_password(self, current_password, new_password):
        self.changed.append((current_password, new_password))
        return {
            "user_id": 42,
            "username": "employee",
            "full_name": "Employee Test",
            "role": "reception",
            "permissions": ["student.read", "student.create"],
            "force_password_change": False,
        }

    def logout(self):
        self.logged_out = True


def test_remote_permission_adapter_preserves_capabilities_without_orm_user():
    client = _Client()
    adapter = ProtectedPermissionServiceAdapter(client)
    user = adapter.authenticate_user("employee", "secret")

    assert user.id == 42
    assert user.role.name == "reception"
    assert user.force_password_change is True
    assert adapter.has_permission("student.read", user)
    assert adapter.has_permission("student.create", user)
    assert not adapter.has_permission("student.delete", user)


def test_remote_password_change_is_scoped_to_authenticated_user():
    client = _Client()
    adapter = ProtectedPermissionServiceAdapter(client)
    user = adapter.authenticate_user("employee", "secret")

    with pytest.raises(AuthenticationError, match="does not belong"):
        adapter.change_password(user.id + 1, "secret", "new-secret")

    updated = adapter.change_password(user.id, "secret", "new-secret")
    assert updated.force_password_change is False
    assert client.changed == [("secret", "new-secret")]

    adapter.logout()
    assert client.logged_out is True
    assert adapter.get_current_user() is None
