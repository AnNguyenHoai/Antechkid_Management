# -*- coding: utf-8 -*-
"""Desktop permission/auth adapter backed by AnTechKidsData.

The adapter exposes the subset of PermissionService required for login and
capability checks without carrying ORM objects or a local SQLAlchemy Session into
the employee process.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from centermanager.core.capabilities import Capability
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.permission_service import AuthenticationError, PermissionDeniedError

from .client import ProtectedDataClient, ProtectedDataClientError


@dataclass
class RemoteRole:
    name: str | None
    permission_names: set[str] = field(default_factory=set)

    def has_permission(self, name: str) -> bool:
        return name in self.permission_names

    def has_any_permission(self, names: Iterable[str]) -> bool:
        return any(name in self.permission_names for name in names)

    def has_all_permissions(self, names: Iterable[str]) -> bool:
        return all(name in self.permission_names for name in names)


@dataclass
class RemoteUserPrincipal:
    id: int
    username: str
    full_name: str
    role: RemoteRole | None
    force_password_change: bool = False
    is_active: bool = True

    @property
    def permissions(self) -> set[str]:
        return set() if self.role is None else set(self.role.permission_names)

    def has_permission(self, name: str) -> bool:
        return bool(self.role and self.role.has_permission(name))

    @property
    def is_admin(self) -> bool:
        return bool(self.role and self.role.name == "admin")

    @property
    def is_teacher(self) -> bool:
        return bool(self.role and self.role.name == "teacher")

    @property
    def is_reception(self) -> bool:
        return bool(self.role and self.role.name == "reception")

    @property
    def is_finance(self) -> bool:
        return bool(self.role and self.role.name == "finance")


class ProtectedPermissionServiceAdapter:
    def __init__(self, client: ProtectedDataClient | None = None) -> None:
        self._client = client or ProtectedDataClient()
        self._current_user: RemoteUserPrincipal | None = None

    @staticmethod
    def _principal(data: dict) -> RemoteUserPrincipal:
        role_name = data.get("role")
        role = RemoteRole(
            name=str(role_name) if role_name else None,
            permission_names={str(value) for value in data.get("permissions", [])},
        ) if role_name else None
        return RemoteUserPrincipal(
            id=int(data["user_id"]),
            username=str(data["username"]),
            full_name=str(data.get("full_name") or data["username"]),
            role=role,
            force_password_change=bool(data.get("force_password_change", False)),
        )

    def authenticate_user(self, username: str, password: str) -> RemoteUserPrincipal:
        try:
            data = self._client.authenticate(username, password)
        except ProtectedDataClientError as exc:
            raise AuthenticationError(str(exc)) from exc
        self._current_user = self._principal(data)
        return self._current_user

    def change_password(self, user_id: int, current_password: str, new_password: str) -> RemoteUserPrincipal:
        if self._current_user is None or int(user_id) != self._current_user.id:
            raise AuthenticationError("Protected session does not belong to this user.")
        try:
            data = self._client.change_password(current_password, new_password)
        except ProtectedDataClientError as exc:
            raise AuthenticationError(str(exc)) from exc
        self._current_user = self._principal(data)
        return self._current_user

    def get_user(self, user_id: int):
        if self._current_user is not None and self._current_user.id == int(user_id):
            return self._current_user
        return None

    def get_current_user(self):
        return self._current_user

    def set_current_user(self, user) -> None:
        self._current_user = user

    def has_permission(self, permission_name: str, user=None) -> bool:
        principal = user or self._current_user
        if principal is None:
            return False
        return AuthorizationService.allows(principal, Capability.from_value(permission_name))

    def has_any_permission(self, permission_names: list[str], user=None) -> bool:
        principal = user or self._current_user
        if principal is None:
            return False
        return AuthorizationService.allows_any(
            principal, [Capability.from_value(name) for name in permission_names]
        )

    def has_all_permissions(self, permission_names: list[str], user=None) -> bool:
        principal = user or self._current_user
        if principal is None:
            return False
        return AuthorizationService.allows_all(
            principal, [Capability.from_value(name) for name in permission_names]
        )

    def require_permission(self, permission_name: str, user=None) -> None:
        if not self.has_permission(permission_name, user):
            raise PermissionDeniedError(f"Capability '{permission_name}' is required.")

    def get_user_permissions(self, user=None) -> set[str]:
        principal = user or self._current_user
        return set() if principal is None else set(principal.permissions)

    def get_user_role(self, user=None):
        principal = user or self._current_user
        return getattr(getattr(principal, "role", None), "name", None)

    def is_admin(self, user=None) -> bool:
        return bool((user or self._current_user) and (user or self._current_user).is_admin)

    def is_teacher(self, user=None) -> bool:
        return bool((user or self._current_user) and (user or self._current_user).is_teacher)

    def is_reception(self, user=None) -> bool:
        return bool((user or self._current_user) and (user or self._current_user).is_reception)

    def logout(self) -> None:
        try:
            self._client.logout()
        finally:
            self._current_user = None
