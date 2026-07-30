# -*- coding: utf-8 -*-
"""
User model - system user with role-based permissions.
"""
from __future__ import annotations

from typing import Optional, List, Set, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.role import Role


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("roles.id"), nullable=True)

    # Relationships
    role: Mapped[Optional[Role]] = relationship("Role", back_populates="users", lazy="selectin")

    __table_args__ = (
        UniqueConstraint('username', name='uq_user_username'),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"

    @property
    def permissions(self) -> Set[str]:
        """Get all permission names for this user via role."""
        if self.role is None:
            return set()
        return self.role.permission_names

    def has_permission(self, permission_name: str) -> bool:
        if self.role is None:
            return False
        return self.role.has_permission(permission_name)

    def has_any_permission(self, permission_names: List[str]) -> bool:
        if self.role is None:
            return False
        return self.role.has_any_permission(permission_names)

    def has_all_permissions(self, permission_names: List[str]) -> bool:
        if self.role is None:
            return False
        return self.role.has_all_permissions(permission_names)

    @property
    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == "admin"

    @property
    def is_teacher(self) -> bool:
        return self.role is not None and self.role.name == "teacher"

    @property
    def is_reception(self) -> bool:
        return self.role is not None and self.role.name == "reception"