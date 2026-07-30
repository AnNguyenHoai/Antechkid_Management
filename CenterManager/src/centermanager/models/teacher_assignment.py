# -*- coding: utf-8 -*-
"""
TeacherAssignment - many-to-many association between teachers and classes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class TeacherAssignment(Base, TimestampMixin):
    __tablename__ = "teacher_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint('teacher_id', 'class_id', name='uq_teacher_class'),
    )

    def __repr__(self) -> str:
        return f"<TeacherAssignment(teacher_id={self.teacher_id}, class_id={self.class_id})>"