# -*- coding: utf-8 -*-
from typing import List, Optional
from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.report import Report
from centermanager.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    def __init__(self, session: Session):
        super().__init__(session, Report)

    def get_by_student(self, student_id: int) -> List[Report]:
        """Get all reports for a student, newest first."""
        return self._session.query(Report).filter(
            Report.student_id == student_id
        ).order_by(desc(Report.generated_at)).all()

    def get_by_student_and_trigger(self, student_id: int, trigger_event: str) -> Optional[Report]:
        """Check if a report with specific trigger exists."""
        return self._session.query(Report).filter(
            Report.student_id == student_id,
            Report.trigger_event == trigger_event
        ).first()


    def exists_for_student_trigger_on_date(
        self, student_id: int, trigger_event: str, target_date: date
    ) -> bool:
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=1)
        return self._session.query(Report.id).filter(
            Report.student_id == student_id,
            Report.trigger_event == trigger_event,
            Report.generated_at >= start,
            Report.generated_at < end,
        ).first() is not None

    def add(self, report: Report) -> Report:
        self._session.add(report)
        return report

    def delete(self, report: Report) -> None:
        self._session.delete(report)