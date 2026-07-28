# -*- coding: utf-8 -*-
"""
Base repository foundation with common operations.
"""
from typing import Generic, TypeVar, Optional, List, Any

from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Generic base repository with common CRUD operations.

    Usage:
        class StudentRepository(BaseRepository[Student]):
            def __init__(self, session: Session):
                super().__init__(session, Student)
    """

    def __init__(self, session: Session, model_class: Any) -> None:
        self._session = session
        self._model_class = model_class

    def add(self, entity: T) -> T:
        """Add an entity to the session."""
        self._session.add(entity)
        return entity

    def get_by_id(self, id_value: int) -> Optional[T]:
        """Get entity by primary key."""
        return self._session.get(self._model_class, id_value)

    def list_all(self) -> List[T]:
        """Get all entities."""
        return self._session.query(self._model_class).all()

    @property
    def session(self) -> Session:
        """Get the underlying session."""
        return self._session