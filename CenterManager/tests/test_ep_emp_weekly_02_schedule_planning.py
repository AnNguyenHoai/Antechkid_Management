from datetime import date, time

import pytest
from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.models.employee import Employee
from centermanager.models.employee_schedule import (
    EmployeeScheduleAssignment,
    EmployeeScheduleRule,
    EmployeeScheduleWeek,
)
from centermanager.models.employee_work_registration import (
    EmployeeWorkRegistration,
    EmployeeWorkRegistrationBlock,
)
from centermanager.models.employee_work_registration_period import (
    EmployeeWorkRegistrationPeriod,
)
from centermanager.services.employee_schedule_service import (
    EmployeeScheduleService,
    EmployeeScheduleValidationError,
)


def _factory(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, Session


def _employee(Session):
    with Session() as session:
        employee = Employee(
            employee_code="EMP-WEEKLY-02",
            full_name="Weekly Planner Employee",
            employment_status=Employee.STATUS_ACTIVE,
        )
        session.add(employee)
        session.commit()
        return employee.id


def _accepted_registration(
    Session,
    employee_id,
    week_start,
    *,
    work_date=None,
    start=time(8, 0),
    end=time(12, 0),
):
    with Session() as session:
        period = EmployeeWorkRegistrationPeriod(week_start=week_start)
        session.add(period)
        session.flush()
        registration = EmployeeWorkRegistration(
            employee_id=employee_id,
            period_id=period.id,
            status=EmployeeWorkRegistration.STATUS_ACCEPTED,
        )
        session.add(registration)
        session.flush()
        session.add(
            EmployeeWorkRegistrationBlock(
                registration_id=registration.id,
                work_date=work_date or week_start,
                start_time=start,
                end_time=end,
                work_type="WORK",
            )
        )
        session.commit()


def _service(Session):
    service = EmployeeScheduleService(Session)
    # Domain tests isolate weekly planning rules from RBAC; permission boundaries
    # remain covered by the existing EmployeeScheduleService test suite.
    service._assert_manage_scope = lambda employee_id, user=None: True
    service._assert_read_scope = lambda employee_id, user=None: True
    return service


def test_week_start_is_monday_and_cross_year_safe():
    assert EmployeeScheduleService.week_start(date(2027, 1, 3)) == date(2026, 12, 28)
    assert EmployeeScheduleService.week_start(date(2026, 12, 28)) == date(2026, 12, 28)


def test_assignment_requires_accepted_registration(test_db_path):
    engine, Session = _factory(test_db_path)
    try:
        employee_id = _employee(Session)
        service = _service(Session)
        with pytest.raises(EmployeeScheduleValidationError, match="no accepted work registration"):
            service.add_week_assignment(
                employee_id,
                date(2026, 9, 28),
                time(9, 0),
                time(11, 0),
                week_start=date(2026, 9, 28),
            )
    finally:
        engine.dispose()


def test_assignment_must_be_inside_accepted_availability_and_not_overlap(test_db_path):
    engine, Session = _factory(test_db_path)
    try:
        employee_id = _employee(Session)
        ws = date(2026, 9, 28)
        _accepted_registration(Session, employee_id, ws)
        service = _service(Session)

        assignment = service.add_week_assignment(
            employee_id,
            ws,
            time(9, 0),
            time(11, 0),
            week_start=ws,
        )
        assert assignment.source == EmployeeScheduleAssignment.SOURCE_MANUAL

        with pytest.raises(EmployeeScheduleValidationError, match="accepted availability"):
            service.add_week_assignment(
                employee_id,
                ws,
                time(12, 0),
                time(13, 0),
                week_start=ws,
            )

        with pytest.raises(EmployeeScheduleValidationError, match="overlaps"):
            service.add_week_assignment(
                employee_id,
                ws,
                time(10, 0),
                time(11, 30),
                week_start=ws,
            )
    finally:
        engine.dispose()


def test_registration_seed_is_idempotent_and_summary_compares_hours(test_db_path):
    engine, Session = _factory(test_db_path)
    try:
        employee_id = _employee(Session)
        ws = date(2026, 9, 28)
        _accepted_registration(Session, employee_id, ws, start=time(8, 0), end=time(12, 0))
        service = _service(Session)

        assert service.seed_week_from_registration(employee_id, ws) == 1
        assert service.seed_week_from_registration(employee_id, ws) == 0

        summary = service.registered_vs_scheduled(employee_id, ws)
        assert summary["registration_status"] == EmployeeWorkRegistration.STATUS_ACCEPTED
        assert summary["registered_hours"] == 4.0
        assert summary["scheduled_hours"] == 4.0
        assert summary["remaining_hours"] == 0.0
        assert summary["assignment_count"] == 1

        with Session() as session:
            week = session.query(EmployeeScheduleWeek).filter_by(week_start=ws).one()
            assert week.status == EmployeeScheduleWeek.STATUS_DRAFT
            assert len(week.assignments) == 1
    finally:
        engine.dispose()


def test_template_seed_only_creates_blocks_covered_by_accepted_registration(test_db_path):
    engine, Session = _factory(test_db_path)
    try:
        employee_id = _employee(Session)
        ws = date(2026, 9, 28)  # Monday
        _accepted_registration(Session, employee_id, ws, start=time(8, 0), end=time(12, 0))
        with Session() as session:
            session.add_all(
                [
                    EmployeeScheduleRule(
                        employee_id=employee_id,
                        day_of_week=0,
                        start_time=time(9, 0),
                        end_time=time(11, 0),
                        effective_from=date(2026, 1, 1),
                    ),
                    EmployeeScheduleRule(
                        employee_id=employee_id,
                        day_of_week=1,
                        start_time=time(9, 0),
                        end_time=time(11, 0),
                        effective_from=date(2026, 1, 1),
                    ),
                ]
            )
            session.commit()

        service = _service(Session)
        result = service.seed_week_from_template(employee_id, ws)
        assert result == {"created": 1, "skipped_outside_availability": 1}
        assert service.seed_week_from_template(employee_id, ws) == {
            "created": 0,
            "skipped_outside_availability": 1,
        }

        rows = service.list_employee_week(employee_id, ws)
        assert len(rows) == 1
        assert rows[0].work_date == ws
        assert rows[0].source == EmployeeScheduleAssignment.SOURCE_TEMPLATE
    finally:
        engine.dispose()


def test_assignment_date_must_belong_to_selected_week(test_db_path):
    engine, Session = _factory(test_db_path)
    try:
        employee_id = _employee(Session)
        ws = date(2026, 12, 28)
        _accepted_registration(
            Session,
            employee_id,
            ws,
            work_date=date(2027, 1, 3),
            start=time(8, 0),
            end=time(12, 0),
        )
        service = _service(Session)

        row = service.add_week_assignment(
            employee_id,
            date(2027, 1, 3),
            time(9, 0),
            time(10, 0),
            week_start=ws,
        )
        assert row.work_date == date(2027, 1, 3)

        with pytest.raises(EmployeeScheduleValidationError, match="selected Monday-Sunday week"):
            service.add_week_assignment(
                employee_id,
                date(2027, 1, 4),
                time(9, 0),
                time(10, 0),
                week_start=ws,
            )
    finally:
        engine.dispose()
