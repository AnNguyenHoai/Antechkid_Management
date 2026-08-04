# src/centermanager/models/user.py
# -*- coding: utf-8 -*-
"""
User model - system user with role-based permissions.
Now includes user management fields.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Set, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, UniqueConstraint, DateTime, Integer
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
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # thêm
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("roles.id"), nullable=True)

    # User management fields
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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

    @property
    def is_finance(self) -> bool:
        return self.role is not None and self.role.name == "finance"

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now() < self.locked_until

    def reset_login_attempts(self) -> None:
        self.login_attempts = 0
        self.locked_until = None

    def increment_login_attempts(self, max_attempts: int = 5, lock_duration_minutes: int = 15) -> None:
        self.login_attempts += 1
        if self.login_attempts >= max_attempts:
            from datetime import timedelta
            self.locked_until = datetime.now() + timedelta(minutes=lock_duration_minutes)