# -*- coding: utf-8 -*-
"""Permission persistence model and compatibility aliases.

The database keeps the existing ``permissions`` table. The authorization
vocabulary itself lives in ``core.capabilities.Capability``.
"""
from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin
from centermanager.core.capabilities import Capability, PERSISTED_CAPABILITIES

if TYPE_CHECKING:
    from centermanager.models.role import Role


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    roles: Mapped[List[Role]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_permission_name"),
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name='{self.name}')>"


class PermissionDefinitions:
    """Backward-compatible names for the canonical capability registry."""

    # Keep historically important source-level aliases explicit. Their values
    # are canonical Capability identifiers; this is not a second vocabulary.
    ROLE_VIEW = "role.view"
    ROLE_MANAGE = "role.manage"
    AUDIT_VIEW = "audit.view"
    SYSTEM_DIAGNOSTICS_VIEW = "system.diagnostics.view"
    BACKUP_VIEW = "backup.view"
    BACKUP_CREATE = "backup.create"
    BACKUP_RESTORE = "backup.restore"
    EMPLOYEE_UPDATE_SELF = "employee.update.self"

    # Every remaining definition is generated from the single canonical enum.
    for _capability in Capability:
        locals().setdefault(_capability.name, _capability.value)
    del _capability

    @classmethod
    def all_permissions(cls) -> List[str]:
        """Return capabilities represented by the generic role matrix."""
        return list(PERSISTED_CAPABILITIES)

    @classmethod
    def get_category(cls, permission_name: str) -> str:
        return Capability.category(permission_name)


# Existing callers can continue importing PermissionName.
PermissionName = PermissionDefinitions
