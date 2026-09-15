from __future__ import annotations
from datetime import date, time
from typing import List, Optional
from sqlalchemy.orm import Session
from centermanager.models.employee_schedule import EmployeeScheduleRule, EmployeeScheduleException

class EmployeeScheduleRepository:
    def __init__(self, session: Session): self._s = session
    def list_rules(self, employee_id: int) -> List[EmployeeScheduleRule]:
        return self._s.query(EmployeeScheduleRule).filter_by(employee_id=employee_id).order_by(EmployeeScheduleRule.day_of_week, EmployeeScheduleRule.start_time, EmployeeScheduleRule.effective_from).all()
    def list_exceptions(self, employee_id: int) -> List[EmployeeScheduleException]:
        return self._s.query(EmployeeScheduleException).filter_by(employee_id=employee_id).order_by(EmployeeScheduleException.schedule_date).all()
    def get_rule(self, rule_id: int) -> Optional[EmployeeScheduleRule]: return self._s.get(EmployeeScheduleRule, rule_id)
    def get_exception(self, exception_id: int) -> Optional[EmployeeScheduleException]: return self._s.get(EmployeeScheduleException, exception_id)

    def add_rule(self, rule: EmployeeScheduleRule) -> EmployeeScheduleRule:
        self._s.add(rule)
        self._s.flush()
        self._s.refresh(rule)
        return rule

    def update_rule(self, rule: EmployeeScheduleRule, *, day_of_week, start_time, end_time, effective_from, effective_to=None, notes=None) -> EmployeeScheduleRule:
        rule.day_of_week = day_of_week
        rule.start_time = start_time
        rule.end_time = end_time
        rule.effective_from = effective_from
        rule.effective_to = effective_to
        rule.notes = notes or None
        self._s.flush()
        self._s.refresh(rule)
        return rule

    def delete_rule(self, rule: EmployeeScheduleRule) -> None:
        self._s.delete(rule)

    def add_exception(self, exception: EmployeeScheduleException) -> EmployeeScheduleException:
        self._s.add(exception)
        self._s.flush()
        self._s.refresh(exception)
        return exception

    def delete_exception(self, exception: EmployeeScheduleException) -> None:
        self._s.delete(exception)
