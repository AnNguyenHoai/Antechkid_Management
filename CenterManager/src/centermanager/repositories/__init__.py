# -*- coding: utf-8 -*-
"""
Data access layer (Repository pattern).
"""
from centermanager.repositories.base import BaseRepository
from centermanager.repositories.student_repository import StudentRepository

__all__ = [
    "BaseRepository",
    "StudentRepository",
]