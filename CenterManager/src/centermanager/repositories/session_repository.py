# -*- coding: utf-8 -*-
"""
Session repository - data access for Session entity.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from centermanager.models.session import Session
from centermanager.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Session)

    def get_by_class(self, class_id: int) -> List[Session]:
        """Get all sessions for a class, ordered by session_number."""
        return self._session.query(Session).filter(
            Session.class_id == class_id
        ).order_by(asc(Session.session_number)).all()

    def get_by_class_ordered_desc(self, class_id: int) -> List[Session]:
        """Get all sessions for a class, newest first."""
        return self._session.query(Session).filter(
            Session.class_id == class_id
        ).order_by(desc(Session.session_number)).all()

    def get_by_id(self, session_id: int) -> Optional[Session]:
        return self._session.get(Session, session_id)

    def get_latest_session_number(self, class_id: int) -> Optional[int]:
        """Get the highest session_number for a class."""
        result = self._session.query(Session.session_number).filter(
            Session.class_id == class_id
        ).order_by(desc(Session.session_number)).first()
        return result[0] if result else None

    def get_sessions_by_date(self, class_id: int, date: date) -> List[Session]:
        """Get sessions for a class on a specific date."""
        return self._session.query(Session).filter(
            Session.class_id == class_id,
            Session.scheduled_date == date
        ).all()

    def add(self, session: Session) -> Session:
        self._session.add(session)
        return session

    def delete(self, session: Session) -> None:
        self._session.delete(session)