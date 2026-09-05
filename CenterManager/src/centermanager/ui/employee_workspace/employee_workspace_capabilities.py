# -*- coding: utf-8 -*-
"""Capability policy for Employee Workspace navigation and actions.

Navigation visibility is derived from explicit capabilities. Read capabilities
never imply write capabilities. Domain services remain responsible for enforcing
these permissions at the data boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService


@dataclass(frozen=True)
class EmployeeWorkspaceCapabilities:
    """Resolved UI capabilities for one authenticated account."""

    management: bool
    employee_view_all: bool
    employee_profile_self: bool
    employee_update_self: bool
    employee_update_all: bool
    employee_create: bool
    employee_archive: bool
    attendance_self: bool
    attendance_all: bool
    attendance_create_self: bool
    attendance_manage: bool
    schedule_self: bool
    schedule_all: bool
    schedule_manage: bool
    registration_self: bool
    registration_all: bool
    registration_manage: bool

    @classmethod
    def resolve(
        cls, permission_service: PermissionService, user: Optional[User]
    ) -> "EmployeeWorkspaceCapabilities":
        """Resolve capabilities without loading employee operational data."""
        if user is None:
            return cls(*(False for _ in range(17)))

        employee_view_all = permission_service.has_permission(
            PermissionDefinitions.EMPLOYEE_VIEW_ALL, user
        )
        manager_or_admin = permission_service.is_admin(user) or bool(
            user.role and user.role.name == RoleDefinitions.MANAGER
        )
        management = employee_view_all or manager_or_admin

        return cls(
            management=management,
            employee_view_all=employee_view_all,
            employee_profile_self=True,
            employee_update_self=permission_service.has_permission(
                PermissionDefinitions.EMPLOYEE_UPDATE_SELF, user
            ),
            employee_update_all=permission_service.has_permission(
                PermissionDefinitions.EMPLOYEE_UPDATE, user
            ),
            employee_create=permission_service.has_permission(
                PermissionDefinitions.EMPLOYEE_CREATE, user
            ),
            employee_archive=permission_service.has_permission(
                PermissionDefinitions.EMPLOYEE_ARCHIVE, user
            ),
            attendance_self=permission_service.has_permission(
                PermissionDefinitions.WORKING_TIME_VIEW_SELF, user
            ),
            attendance_all=permission_service.has_permission(
                PermissionDefinitions.WORKING_TIME_VIEW_ALL, user
            ),
            attendance_create_self=permission_service.has_permission(
                PermissionDefinitions.WORKING_TIME_CREATE_SELF, user
            ),
            attendance_manage=permission_service.has_permission(
                PermissionDefinitions.WORKING_TIME_MANAGE, user
            ),
            schedule_self=permission_service.has_permission(
                PermissionDefinitions.SCHEDULE_VIEW_SELF, user
            ),
            schedule_all=permission_service.has_permission(
                PermissionDefinitions.SCHEDULE_VIEW_ALL, user
            ),
            schedule_manage=permission_service.has_permission(
                PermissionDefinitions.SCHEDULE_MANAGE, user
            ),
            registration_self=permission_service.has_any_permission(
                [
                    PermissionDefinitions.WORK_REGISTRATION_SELF,
                    "working_time.registration.self",
                ],
                user,
            ),
            registration_all=permission_service.has_permission(
                PermissionDefinitions.WORK_REGISTRATION_VIEW_ALL, user
            ),
            registration_manage=permission_service.has_permission(
                PermissionDefinitions.WORK_REGISTRATION_MANAGE, user
            ),
        )

    def self_nav_items(self) -> list[dict]:
        """Return only self-service destinations the account can actually load."""
        items = [{"id": "profile", "icon": "👤", "label": "My Profile"}]
        if self.attendance_self:
            items.append({"id": "attendance", "icon": "🕒", "label": "Attendance"})
        if self.registration_self:
            items.append({"id": "registration", "icon": "📝", "label": "Work Registration"})
        if self.schedule_self:
            items.append({"id": "schedule", "icon": "📅", "label": "Schedule"})
        return items

    def management_nav_items(self) -> list[dict]:
        """Return management destinations without duplicate self/all registration entries."""
        items = []
        if self.management:
            items.append({"id": "employees", "icon": "👥", "label": "Employees"})
        if self.registration_all:
            items.append({"id": "registrations", "icon": "📝", "label": "Work Registrations"})
        elif self.registration_self:
            items.append({"id": "my_registration", "icon": "👤", "label": "My Work Registration"})
        return items

    def can_edit_profile(self, is_self: bool) -> bool:
        """Return whether the profile editor may enable its write controls."""
        return self.employee_update_self if is_self else self.employee_update_all

    def can_edit_schedule(self) -> bool:
        return self.schedule_manage

    def can_edit_working_time(self, is_self: bool) -> bool:
        return self.attendance_create_self if is_self else self.attendance_manage

    def can_manage_registration(self) -> bool:
        return self.registration_manage
