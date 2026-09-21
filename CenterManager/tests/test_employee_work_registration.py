from datetime import date, time, datetime, timedelta
import pytest
from sqlalchemy.orm import sessionmaker
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import User, Role, Permission, EmployeeWorkRegistration
from centermanager.models.audit_log import AuditLog
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.services.employee_service import EmployeeService
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService, EmployeeWorkRegistrationValidationError, EmployeeWorkRegistrationAccessDeniedError
from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.core.current_user import CurrentUserContext


@pytest.fixture(autouse=True)
def fixed_application_clock():
    set_clock(Clock(now_fn=lambda: datetime(2026, 8, 31, 10, 0, 0), today_fn=lambda: date(2026, 8, 31)))
    try:
        yield
    finally:
        reset_clock()


def setup_db(tmp_path):
    engine = create_engine_for_path(tmp_path / 'registration.db')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        manager_role = Role(name='manager', display_name='Manager', is_system=True)
        p_all = Permission(name='work_registration.view.all', description='view all', category='employee')
        p_manage = Permission(name='work_registration.manage', description='manage', category='employee')
        manager_role.permissions.extend([p_all, p_manage])
        role = Role(name='teacher', display_name='Teacher', is_system=True)
        p = Permission(name='working_time.registration.self', description='register', category='employee')
        role.permissions.append(p)
        other_role = Role(name='teacher2', display_name='Teacher 2', is_system=True)
        other_role.permissions.append(p)
        s.add_all([manager_role, role, other_role]); s.flush()
        manager = User(username='manager', password_hash='x', full_name='Manager', role_id=manager_role.id, is_active=True, force_password_change=False)
        u = User(username='teacher', password_hash='x', full_name='Teacher', role_id=role.id, is_active=True, force_password_change=False)
        u2 = User(username='teacher2', password_hash='x', full_name='Teacher2', role_id=other_role.id, is_active=True, force_password_change=False)
        s.add_all([manager, u, u2]); s.flush(); s.commit(); s.refresh(manager); s.refresh(u); s.refresh(u2)
    es = EmployeeService(Session)
    with CurrentUserContext(manager): emp = es.create_employee('Teacher', user_id=u.id)
    with CurrentUserContext(manager): other = es.create_employee('Teacher2', user_id=u2.id)
    return Session, u, u2, emp, other


def _next_week(svc):
    return svc.next_week()


def test_registration_is_next_week_only_and_separate_from_actual(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        ws = _next_week(svc)
        r = svc.create(emp.id, ws, time(9), time(12), 'TEACHING')
        assert r.status == 'DRAFT'
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.submit(r.id)
        svc.submit_week(emp.id, ws)
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id, date(2026, 8, 31), time(9), time(12), 'WORK')
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id, ws, time(11), time(13), 'WORK')


def test_registration_is_own_employee_only(tmp_path):
    Session, u, _, _, other = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_for_employee(other.id, _next_week(svc))


def test_employee_can_submit_entire_next_week_registration(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        ws = _next_week(svc)
        svc.create(emp.id, ws, time(9), time(12), 'WORK')
        svc.create(emp.id, ws + timedelta(days=1), time(13), time(17), 'WORK')
        registration = svc.submit_week(emp.id, ws)
        assert registration.status == EmployeeWorkRegistration.STATUS_SUBMITTED
        assert len(registration.blocks) == 2
        assert all(block.registration_id == registration.id for block in registration.blocks)


def test_manager_can_view_all_and_close_submitted_registrations(tmp_path):
    Session, u, u2, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        ws = _next_week(svc)
        svc.create(emp.id, ws, time(9), time(12), 'WORK'); svc.submit_week(emp.id, ws)
    with CurrentUserContext(u2):
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_all(ws)
    with Session() as s: manager = s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager):
        rows = svc.list_all(ws)
        assert len(rows) == 1 and rows[0].employee_id == emp.id
        accepted = svc.accept(emp.id, ws)
        assert accepted.status == EmployeeWorkRegistration.STATUS_ACCEPTED
        assert svc.close_week(ws) == 1
        assert svc.get_period(ws, manager).status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
        assert svc.list_all(ws)[0].status == EmployeeWorkRegistration.STATUS_ACCEPTED


def test_manager_permission_is_required_even_for_manager_role(tmp_path):
    Session, _, _, _, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session)
    with Session() as s:
        manager = s.query(User).filter_by(username='manager').one(); manager.role.permissions.clear(); s.commit(); s.refresh(manager)
    with CurrentUserContext(manager):
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_all(_next_week(svc))


def test_close_week_requires_accepted_registrations_and_closes_period(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session); ws = _next_week(svc)
    with CurrentUserContext(u): svc.create(emp.id, ws, time(9), time(12), 'WORK')
    with Session() as s: manager = s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager):
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.close_week(ws)
    with CurrentUserContext(u): svc.submit_week(emp.id, ws)
    with CurrentUserContext(manager):
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.close_week(ws)
        svc.accept(emp.id, ws)
        assert svc.close_week(ws) == 1
        assert svc.get_period(ws, manager).status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED


def test_closed_period_blocks_new_registration(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session); ws = _next_week(svc)
    with CurrentUserContext(u): svc.create(emp.id, ws, time(9), time(12), 'WORK'); svc.submit_week(emp.id, ws)
    with Session() as s: manager = s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager): svc.accept(emp.id, ws); svc.close_week(ws)
    with CurrentUserContext(u):
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id, ws + timedelta(days=1), time(13), time(17), 'WORK')


def test_audit_records_submission_and_period_close(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session); ws = _next_week(svc)
    with CurrentUserContext(u): svc.create(emp.id, ws, time(9), time(12), 'WORK'); svc.submit_week(emp.id, ws)
    with Session() as s: manager = s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager): svc.accept(emp.id, ws); svc.close_week(ws)
    with Session() as s: actions = [row.action for row in s.query(AuditLog).all()]
    assert 'WORK_REGISTRATION_CREATED' in actions
    assert 'WORK_REGISTRATION_SUBMITTED' in actions
    assert 'WORK_REGISTRATION_PERIOD_CLOSED' in actions


def test_close_week_audit_records_canonical_entity_metadata(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session); ws = _next_week(svc)
    with CurrentUserContext(u): svc.create(emp.id, ws, time(9), time(12), 'WORK'); svc.submit_week(emp.id, ws)
    with Session() as s: manager = s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager): svc.accept(emp.id, ws); svc.close_week(ws)
    with Session() as s:
        close_log = s.query(AuditLog).filter_by(action='WORK_REGISTRATION_PERIOD_CLOSED').one()
        period = s.query(EmployeeWorkRegistrationPeriod).filter_by(week_start=ws).one()
        assert close_log.entity_type == 'EmployeeWorkRegistrationPeriod'
        assert close_log.entity_id == str(period.id)
        assert close_log.target_type == close_log.entity_type
        assert close_log.target_id == close_log.entity_id


def test_manager_list_all_keeps_employee_relationship_loaded_after_service_session_closes(tmp_path):
    Session, u, _, emp, _ = setup_db(tmp_path); svc = EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        ws = _next_week(svc); svc.create(emp.id, ws, time(9), time(12), 'WORK'); svc.submit_week(emp.id, ws)
    with Session() as s: manager = s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager): rows = svc.list_all(ws)
    assert len(rows) == 1
    assert rows[0].employee is not None
    assert rows[0].employee.employee_code == emp.employee_code
