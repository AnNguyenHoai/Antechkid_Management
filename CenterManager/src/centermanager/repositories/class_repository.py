# -*- coding: utf-8 -*-
"""
Class repository - data access for Class entity.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from centermanager.models.class_ import Class
from centermanager.repositories.base import BaseRepository


class ClassRepository(BaseRepository[Class]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Class)

    def get_by_name(self, name: str) -> Optional[Class]:
        return self._session.query(Class).filter(Class.name == name).first()

    def list_all(self) -> List[Class]:
        return self._session.query(Class).all()