from datetime import date, datetime, time

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.core.current_user import CurrentUserContext
from centermanager.models.audit_log import AuditLog
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.services.audit_service import AuditService
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService
from .test_employee_work_registration import setup_db


def test_audit_service_always_populates_summary(tmp_path):
    Session, user, *_ = setup_db(tmp_path)
    service = AuditService(Session)

    with CurrentUserContext(user):
        log = service.record(
            "TEST_AUDIT_SUMMARY",
            "test",
            target_type="ExampleEntity",
            target_id=7,
        )

    assert log.summary == "TEST_AUDIT_SUMMARY: ExampleEntity#7"
    with Session() as session:
        persisted = session.get(AuditLog, log.id)
        assert persisted.summary == "TEST_AUDIT_SUMMARY: ExampleEntity#7"


def test_close_month_persists_summary_and_entity_identity(tmp_path):
    fixed_now = datetime(2026, 8, 31, 10, 30, 0)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_now.date()))
    try:
        Session, user, _, employee, _ = setup_db(tmp_path)
        service = EmployeeWorkRegistrationService(Session)
        year, month = service.next_month()

        with CurrentUserContext(user):
            service.create(employee.id, date(year, month, 5), time(9), time(12), "WORK")
            service.submit_month(employee.id, year, month)

        with Session() as session:
            manager = session.query(__import__("centermanager.models", fromlist=["User"]).User).filter_by(username="manager").one()

        with CurrentUserContext(manager):
            service.accept(employee.id, year, month)
            service.close_month(year, month)

        with Session() as session:
            log = session.query(AuditLog).filter_by(action=service.AUDIT_CLOSED).one()
            period = session.query(EmployeeWorkRegistrationPeriod).filter_by(year=year, month=month).one()

            assert log.summary == f"WORK_REGISTRATION_PERIOD_CLOSED: EmployeeWorkRegistrationPeriod#{period.id}"
            assert log.entity_type == "EmployeeWorkRegistrationPeriod"
            assert log.entity_id == str(period.id)
            assert log.target_type == log.entity_type
            assert log.target_id == log.entity_id
    finally:
        reset_clock()
