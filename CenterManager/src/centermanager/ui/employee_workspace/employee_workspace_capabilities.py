# -*- coding: utf-8 -*-
"""Capability policy for Employee Workspace navigation.

The workspace uses capabilities for navigation visibility. Domain services remain
responsible for enforcing the same permissions at the data boundary.
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
    attendance_self: bool
    attendance_all: bool
    schedule_self: bool
    schedule_all: bool
    registration_self: bool
    registration_all: bool

    @classmethod
    def resolve(cls, permission_service: PermissionService, user: Optional[User]) -> "EmployeeWorkspaceCapabilities":
        """Resolve capabilities without loading employee operational data."""
        if user is None:
            return cls(False, False, False, False, False, False, False, False, False)

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
            # Profile is the baseline self-service destination. The service
            # still enforces the actual employee identity/data boundary.
            employee_profile_self=True,
            attendance_self=permission_service.has_permission(
                PermissionDefinitions.WORKING_TIME_VIEW_SELF, user
            ),
            attendance_all=permission_service.has_permission(
                PermissionDefinitions.WORKING_TIME_VIEW_ALL, user
            ) or manager_or_admin,
            schedule_self=permission_service.has_permission(
                PermissionDefinitions.SCHEDULE_VIEW_SELF, user
            ),
            schedule_all=permission_service.has_permission(
                PermissionDefinitions.SCHEDULE_VIEW_ALL, user
            ) or manager_or_admin,
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
            # A management account without all-scope review access may still
            # need its own registration, but an account with all-scope access
            # already has the broader Work Registrations destination.
            items.append({"id": "my_registration", "icon": "👤", "label": "My Work Registration"})
        return items
