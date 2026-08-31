# -*- coding: utf-8 -*-
from datetime import date
from typing import Optional, List
from sqlalchemy.orm import sessionmaker
from centermanager.models.employee import Employee
from centermanager.repositories.employee_repository import EmployeeRepository
class EmployeeServiceError(Exception): pass
class EmployeeNotFoundError(EmployeeServiceError): pass
class EmployeeValidationError(EmployeeServiceError): pass
class EmployeeService:
    def __init__(self, session_factory: sessionmaker): self._session_factory=session_factory
    @staticmethod
    def _text(v):
        if v is None:return None
        v=v.strip(); return v or None
    def _validate_status(self,status):
        status=(self._text(status) or Employee.STATUS_ACTIVE).upper()
        if status not in Employee.VALID_STATUSES: raise EmployeeValidationError(f'Invalid employment status: {status}')
        return status
    def create_employee(self, full_name:str, *, date_of_birth:Optional[date]=None, gender=None, phone=None, email=None, address=None, department=None, position=None, employment_status=Employee.STATUS_ACTIVE, hire_date:Optional[date]=None, user_id:Optional[int]=None)->Employee:
        full_name=self._text(full_name)
        if not full_name: raise EmployeeValidationError('Full name is required.')
        if email:=self._text(email):
            if '@' not in email: raise EmployeeValidationError('Invalid email format.')
        status=self._validate_status(employment_status)
        with self._session_factory() as s:
            repo=EmployeeRepository(s)
            if user_id is not None and repo.get_by_user_id(user_id): raise EmployeeValidationError('User is already linked to an employee.')
            n=(repo.get_highest_employee_number() or 0)+1
            e=Employee(employee_code=f'EMP-{n:05d}',full_name=full_name,date_of_birth=date_of_birth,gender=self._text(gender),phone=self._text(phone),email=email,address=self._text(address),department=self._text(department),position=self._text(position),employment_status=status,hire_date=hire_date or date.today(),user_id=user_id)
            repo.add(e); s.commit(); s.refresh(e); return e
    def get_employee(self, employee_id:int)->Employee:
        with self._session_factory() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeNotFoundError(f'Employee {employee_id} not found.')
            return e
    def list_employees(self)->List[Employee]:
        with self._session_factory() as s:return EmployeeRepository(s).list_all()
    def update_status(self, employee_id:int, status:str, termination_date:Optional[date]=None)->Employee:
        with self._session_factory() as s:
            e=EmployeeRepository(s).get_by_id(employee_id)
            if not e: raise EmployeeNotFoundError(f'Employee {employee_id} not found.')
            e.employment_status=self._validate_status(status); e.termination_date=termination_date
            s.commit(); s.refresh(e); return e
