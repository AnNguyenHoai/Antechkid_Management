# -*- coding: utf-8 -*-
from typing import Optional, List
from sqlalchemy.orm import Session
from centermanager.models.employee import Employee
from centermanager.repositories.base import BaseRepository
class EmployeeRepository(BaseRepository[Employee]):
    def __init__(self, session: Session): super().__init__(session, Employee)
    def get_by_code(self, code: str) -> Optional[Employee]: return self._session.query(Employee).filter(Employee.employee_code==code).first()
    def get_by_user_id(self, user_id: int) -> Optional[Employee]: return self._session.query(Employee).filter(Employee.user_id==user_id).first()
    def list_all(self) -> List[Employee]: return self._session.query(Employee).order_by(Employee.employee_code).all()
    def get_highest_employee_number(self) -> Optional[int]:
        rows=self._session.query(Employee.employee_code).all(); nums=[]
        for (code,) in rows:
            if code.startswith('EMP-') and code[4:].isdigit(): nums.append(int(code[4:]))
        return max(nums) if nums else None
