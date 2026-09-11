from __future__ import annotations
from datetime import date
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
