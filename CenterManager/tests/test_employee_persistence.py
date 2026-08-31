# -*- coding: utf-8 -*-
"""Employee persistence regression tests."""
from datetime import date

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models import Employee, EmployeeDocument  # ensure registry coverage
from centermanager.services.employee_service import EmployeeService
from sqlalchemy.orm import sessionmaker


def test_employee_document_is_registered_in_metadata():
    assert "employee_documents" in Base.metadata.tables


def test_employee_service_can_create_employee(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    service = EmployeeService(Session)
    employee = service.create_employee(
        "Regression Employee",
        phone="0900000000",
        hire_date=date(2026, 8, 31),
    )

    assert employee.id is not None
    assert employee.employee_code == "EMP-00001"
    assert employee.created_at is not None
    assert employee.updated_at is not None
