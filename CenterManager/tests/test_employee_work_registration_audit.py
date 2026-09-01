from datetime import date, datetime, time
from unittest.mock import patch

import pytest

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.core.current_user import CurrentUserContext
from centermanager.models.audit_log import AuditLog
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService
from test_employee_work_registration import setup_db


@pytest.fixture(autouse=True)
def fixed_application_clock():
    set_clock(Clock(now_fn=lambda: datetime(2026, 8, 31, 10, 30, 0), today_fn=lambda: date(2026, 8, 31)))
    try:
        yield
    finally:
        reset_clock()


def _audit_rows(Session):
    with Session() as s:
        return s.query(AuditLog).order_by(AuditLog.id).all()


def test_work_registration_audit_is_atomic_and_uses_application_clock(tmp_path):
    Session, u, u2, emp, other = setup_db(tmp_path)
    svc = EmployeeWorkRegistrationService(Session)

    with CurrentUserContext(u):
        y, m = svc.next_month()
        registration = svc.create(emp.id, date(y, m, 5), time(9), time(12), 'WORK')

    rows = _audit_rows(Session)
    assert [(row.action, row.created_at) for row in rows] == [
        ('WORK_REGISTRATION_CREATED', datetime(2026, 8, 31, 10, 30, 0))
    ]
    assert rows[0].actor_id == u.id
    assert rows[0].target_type == 'EmployeeWorkRegistration'
    assert rows[0].target_id == str(registration.id)
    assert rows[0].module == EmployeeWorkRegistrationService.AUDIT_MODULE

    with CurrentUserContext(u):
        svc.submit_month(emp.id, y, m)
    with Session() as s:
        manager = s.query(__import__('centermanager.models', fromlist=['User']).User).filter_by(username='manager').one()
    with CurrentUserContext(manager):
        svc.accept(emp.id, y, m)
        svc.close_month(y, m)

    assert [row.action for row in _audit_rows(Session)] == [
        'WORK_REGISTRATION_CREATED',
        'WORK_REGISTRATION_SUBMITTED',
        'WORK_REGISTRATION_ACCEPTED',
        'WORK_REGISTRATION_PERIOD_CLOSED',
    ]
    assert all(row.created_at == datetime(2026, 8, 31, 10, 30, 0) for row in _audit_rows(Session))


def test_work_registration_audit_failure_rolls_back_business_mutation(tmp_path):
    Session, u, u2, emp, other = setup_db(tmp_path)
    svc = EmployeeWorkRegistrationService(Session)

    with patch.object(svc._audit_service, 'record_in_session', side_effect=RuntimeError('audit unavailable')):
        with CurrentUserContext(u):
            y, m = svc.next_month()
            with pytest.raises(RuntimeError, match='audit unavailable'):
                svc.create(emp.id, date(y, m, 5), time(9), time(12), 'WORK')

    with Session() as s:
        assert s.query(EmployeeWorkRegistration).count() == 0
        assert s.query(AuditLog).count() == 0


def test_work_registration_mutations_emit_update_delete_reopen_and_deadline_audits(tmp_path):
    Session, u, u2, emp, other = setup_db(tmp_path)
    svc = EmployeeWorkRegistrationService(Session)

    with CurrentUserContext(u):
        y, m = svc.next_month()
        registration = svc.create(emp.id, date(y, m, 5), time(9), time(12), 'WORK')
        block_id = registration.blocks[0].id
        svc.update(block_id, work_date=date(y, m, 5), start_time=time(10), end_time=time(12), work_type='WORK-UPDATED')
        svc.delete(block_id)
        registration = svc.create(emp.id, date(y, m, 6), time(9), time(12), 'WORK')
        svc.submit_month(emp.id, y, m)

    with Session() as s:
        manager = s.query(__import__('centermanager.models', fromlist=['User']).User).filter_by(username='manager').one()
    with CurrentUserContext(manager):
        svc.accept(emp.id, y, m)
        svc.reopen(emp.id, y, m)
        svc.set_submission_deadline(y, m, date(y, m, 20))

    assert [row.action for row in _audit_rows(Session)] == [
        'WORK_REGISTRATION_CREATED',
        'WORK_REGISTRATION_UPDATED',
        'WORK_REGISTRATION_DELETED',
        'WORK_REGISTRATION_CREATED',
        'WORK_REGISTRATION_SUBMITTED',
        'WORK_REGISTRATION_ACCEPTED',
        'WORK_REGISTRATION_REOPENED',
        'WORK_REGISTRATION_DEADLINE_UPDATED',
    ]
