# -*- coding: utf-8 -*-
"""
Role model - defines system roles with permissions.
"""
from __future__ import annotations

from typing import Optional, List, Set, TYPE_CHECKING

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.user import User
    from centermanager.models.permission import Permission


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False)

    # Relationships
    users: Mapped[List[User]] = relationship("User", back_populates="role")
    permissions: Mapped[List[Permission]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin"  # lazy loading thay vì joinedload mặc định
    )

    __table_args__ = (
        UniqueConstraint('name', name='uq_role_name'),
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"

    def has_permission(self, permission_name: str) -> bool:
        return any(p.name == permission_name for p in self.permissions)

    def has_any_permission(self, permission_names: List[str]) -> bool:
        return any(self.has_permission(p) for p in permission_names)

    def has_all_permissions(self, permission_names: List[str]) -> bool:
        return all(self.has_permission(p) for p in permission_names)

    @property
    def permission_names(self) -> Set[str]:
        return {p.name for p in self.permissions}


# Role definitions
class RoleDefinitions:
    ADMIN = "admin"
    TEACHER = "teacher"
    RECEPTION = "reception"
    FINANCE = "finance"
    MANAGER = "manager"   # Thêm

    @classmethod
    def all_roles(cls) -> List[str]:
        return [cls.ADMIN, cls.TEACHER, cls.RECEPTION, cls.FINANCE, cls.MANAGER]

    @classmethod
    def get_display_name(cls, role_name: str) -> str:
        display_map = {
            cls.ADMIN: "Administrator",
            cls.TEACHER: "Teacher",
            cls.RECEPTION: "Reception",
            cls.FINANCE: "Finance",
            cls.MANAGER: "Manager",   # Thêm
        }
        return display_map.get(role_name, role_name.capitalize())