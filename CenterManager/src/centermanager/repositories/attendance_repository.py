# -*- coding: utf-8 -*-
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func

from centermanager.models.attendance import Attendance
from centermanager.models.session import Session  # Import Session để dùng trong joinedload
from centermanager.repositories.base import BaseRepository


class AttendanceRepository(BaseRepository[Attendance]):
    def __init__(self, session: Session):
        super().__init__(session, Attendance)

    def get_by_session(self, session_id: int) -> List[Attendance]:
        return (
            self._session.query(Attendance)
            .options(
                joinedload(Attendance.session).joinedload(Session.class_)
            )
            .filter(Attendance.session_id == session_id)
            .order_by(Attendance.student_id)
            .all()
        )

    def get_by_student(self, student_id: int) -> List[Attendance]:
        return (
            self._session.query(Attendance)
            .options(
                joinedload(Attendance.session).joinedload(Session.class_)
            )
            .filter(Attendance.student_id == student_id)
            .order_by(desc(Attendance.created_at))
            .all()
        )

    def get_by_session_and_student(self, session_id: int, student_id: int) -> Optional[Attendance]:
        return (
            self._session.query(Attendance)
            .options(
                joinedload(Attendance.session).joinedload(Session.class_)
            )
            .filter(
                Attendance.session_id == session_id,
                Attendance.student_id == student_id
            )
            .first()
        )

    def get_summary_by_session(self, session_id: int) -> Dict[str, int]:
        results = (
            self._session.query(Attendance.status, func.count(Attendance.id))
            .filter(Attendance.session_id == session_id)
            .group_by(Attendance.status)
            .all()
        )
        summary = {status: 0 for status in ["Present", "Late", "Absent", "Excused"]}
        for status, count in results:
            summary[status] = count
        return summary

    def add(self, attendance: Attendance) -> Attendance:
        self._session.add(attendance)
        return attendance

    def delete(self, attendance: Attendance) -> None:
        self._session.delete(attendance)