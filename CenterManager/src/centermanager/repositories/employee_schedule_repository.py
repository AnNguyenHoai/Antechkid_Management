from __future__ import annotations
from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from centermanager.models.employee_schedule import (
    EmployeeScheduleRule,
    EmployeeScheduleException,
    EmployeeScheduleWeek,
    EmployeeScheduleAssignment,
)


class EmployeeScheduleRepository:
    def __init__(self, session: Session):
        self._session = session

    # ------------------------------------------------------------------
    # Schedule Template (legacy recurring rules + date exceptions)
    # ------------------------------------------------------------------
    def list_rules(self, employee_id: int) -> List[EmployeeScheduleRule]:
        return (
            self._session.query(EmployeeScheduleRule)
            .filter_by(employee_id=employee_id)
            .order_by(
                EmployeeScheduleRule.day_of_week,
                EmployeeScheduleRule.start_time,
                EmployeeScheduleRule.effective_from,
            )
            .all()
        )

    def list_exceptions(self, employee_id: int) -> List[EmployeeScheduleException]:
        return (
            self._session.query(EmployeeScheduleException)
            .filter_by(employee_id=employee_id)
            .order_by(EmployeeScheduleException.schedule_date)
            .all()
        )

    def get_rule(self, rule_id: int) -> Optional[EmployeeScheduleRule]:
        return self._session.get(EmployeeScheduleRule, rule_id)

    def get_exception(self, exception_id: int) -> Optional[EmployeeScheduleException]:
        return self._session.get(EmployeeScheduleException, exception_id)

    def add_rule(self, rule: EmployeeScheduleRule) -> EmployeeScheduleRule:
        self._session.add(rule)
        self._session.flush()
        self._session.refresh(rule)
        return rule

    def update_rule(
        self,
        rule: EmployeeScheduleRule,
        *,
        day_of_week,
        start_time,
        end_time,
        effective_from,
        effective_to=None,
        notes=None,
    ) -> EmployeeScheduleRule:
        rule.day_of_week = day_of_week
        rule.start_time = start_time
        rule.end_time = end_time
        rule.effective_from = effective_from
        rule.effective_to = effective_to
        rule.notes = notes or None
        self._session.flush()
        self._session.refresh(rule)
        return rule

    def delete_rule(self, rule: EmployeeScheduleRule) -> None:
        self._session.delete(rule)

    def add_exception(self, exception: EmployeeScheduleException) -> EmployeeScheduleException:
        self._session.add(exception)
        self._session.flush()
        self._session.refresh(exception)
        return exception

    def delete_exception(self, exception: EmployeeScheduleException) -> None:
        self._session.delete(exception)

    # ------------------------------------------------------------------
    # Weekly operational schedule draft
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_week_start(value: date) -> date:
        if not isinstance(value, date):
            raise ValueError("week_start must be a date")
        return value - timedelta(days=value.weekday())

    def get_week(self, week_start: date) -> Optional[EmployeeScheduleWeek]:
        week_start = self.normalize_week_start(week_start)
        return self._session.scalar(
            select(EmployeeScheduleWeek)
            .options(joinedload(EmployeeScheduleWeek.assignments))
            .where(EmployeeScheduleWeek.week_start == week_start)
        )

    def get_or_create_week(self, week_start: date) -> EmployeeScheduleWeek:
        week_start = self.normalize_week_start(week_start)
        week = self.get_week(week_start)
        if week is None:
            week = EmployeeScheduleWeek(week_start=week_start)
            self._session.add(week)
            self._session.flush()
        return week

    def get_assignment(self, assignment_id: int) -> Optional[EmployeeScheduleAssignment]:
        return self._session.scalar(
            select(EmployeeScheduleAssignment)
            .options(joinedload(EmployeeScheduleAssignment.employee))
            .where(EmployeeScheduleAssignment.id == assignment_id)
        )

    def list_week_assignments(self, week_start: date) -> List[EmployeeScheduleAssignment]:
        week_start = self.normalize_week_start(week_start)
        week = self._session.scalar(
            select(EmployeeScheduleWeek).where(EmployeeScheduleWeek.week_start == week_start)
        )
        if week is None:
            return []
        return list(
            self._session.scalars(
                select(EmployeeScheduleAssignment)
                .options(joinedload(EmployeeScheduleAssignment.employee))
                .where(EmployeeScheduleAssignment.schedule_week_id == week.id)
                .order_by(
                    EmployeeScheduleAssignment.work_date,
                    EmployeeScheduleAssignment.employee_id,
                    EmployeeScheduleAssignment.start_time,
                )
            ).all()
        )

    def list_employee_week(
        self, employee_id: int, week_start: date
    ) -> List[EmployeeScheduleAssignment]:
        week_start = self.normalize_week_start(week_start)
        week = self._session.scalar(
            select(EmployeeScheduleWeek).where(EmployeeScheduleWeek.week_start == week_start)
        )
        if week is None:
            return []
        return list(
            self._session.scalars(
                select(EmployeeScheduleAssignment)
                .options(joinedload(EmployeeScheduleAssignment.employee))
                .where(
                    EmployeeScheduleAssignment.schedule_week_id == week.id,
                    EmployeeScheduleAssignment.employee_id == employee_id,
                )
                .order_by(
                    EmployeeScheduleAssignment.work_date,
                    EmployeeScheduleAssignment.start_time,
                )
            ).all()
        )

    def add_assignment(
        self, assignment: EmployeeScheduleAssignment
    ) -> EmployeeScheduleAssignment:
        self._session.add(assignment)
        self._session.flush()
        self._session.refresh(assignment)
        return assignment

    def delete_assignment(self, assignment: EmployeeScheduleAssignment) -> None:
        self._session.delete(assignment)
