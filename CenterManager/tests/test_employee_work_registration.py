from datetime import date, time
import pytest
from sqlalchemy.orm import sessionmaker
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import User, Role, Employee, Permission
from centermanager.services.employee_service import EmployeeService
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService, EmployeeWorkRegistrationValidationError, EmployeeWorkRegistrationAccessDeniedError
from centermanager.core.current_user import CurrentUserContext


def setup_db(tmp_path):
    engine=create_engine_for_path(tmp_path/'registration.db'); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as s:
        manager_role=Role(name='manager',display_name='Manager',is_system=True)
        p_all=Permission(name='work_registration.view.all',description='view all',category='employee')
        p_manage=Permission(name='work_registration.manage',description='manage',category='employee')
        manager_role.permissions.extend([p_all,p_manage])
        role=Role(name='teacher',display_name='Teacher',is_system=True)
        p=Permission(name='working_time.registration.self',description='register',category='employee'); role.permissions.append(p)
        other_role=Role(name='teacher2',display_name='Teacher 2',is_system=True); other_role.permissions.append(p)
        s.add_all([manager_role,role,other_role]);s.flush()
        manager=User(username='manager',password_hash='x',full_name='Manager',role_id=manager_role.id,is_active=True,force_password_change=False)
        u=User(username='teacher',password_hash='x',full_name='Teacher',role_id=role.id,is_active=True,force_password_change=False)
        u2=User(username='teacher2',password_hash='x',full_name='Teacher2',role_id=other_role.id,is_active=True,force_password_change=False)
        s.add_all([manager,u,u2]);s.flush();s.commit();s.refresh(manager);s.refresh(u);s.refresh(u2)
    es=EmployeeService(Session)
    with CurrentUserContext(manager): emp=es.create_employee('Teacher',user_id=u.id)
    with CurrentUserContext(manager): other=es.create_employee('Teacher2',user_id=u2.id)
    return Session,u,u2,emp,other


def test_registration_is_next_month_only_and_separate_from_actual(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        y,m=svc.next_month(date(2026,8,31)); r=svc.create(emp.id,date(y,m,3),time(9),time(12),'TEACHING')
        assert r.status=='DRAFT'
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.submit(r.id)
        svc.submit_month(emp.id, y, m)
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id,date(2026,8,31),time(9),time(12),'WORK')
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id,date(y,m,3),time(11),time(13),'WORK')


def test_registration_is_own_employee_only(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_for_employee(other.id,*svc.next_month(date(2026,8,31)))

def test_employee_can_submit_entire_next_month_registration(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        y,m=svc.next_month(date(2026,8,31))
        svc.create(emp.id,date(y,m,3),time(9),time(12),'WORK')
        svc.create(emp.id,date(y,m,4),time(13),time(17),'WORK')
        rows=svc.submit_month(emp.id,y,m)
        assert len(rows)==2
        assert {r.status for r in rows}=={'SUBMITTED'}


def test_manager_can_view_all_and_close_submitted_registrations(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        y,m=svc.next_month(date(2026,8,31))
        svc.create(emp.id,date(y,m,3),time(9),time(12),'WORK')
        svc.submit_month(emp.id,y,m)
    with CurrentUserContext(u2):
        # u2 is not manager in the fixture; this verifies self-scope remains enforced.
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_all(y,m)
    with Session() as s:
        manager=s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager):
        rows=svc.list_all(y,m)
        assert len(rows)==1 and rows[0].employee_id==emp.id
        assert svc.close_month(y,m)==1
        rows=svc.list_all(y,m)
        assert rows[0].status=='CLOSED'



def test_manager_permission_is_required_even_for_manager_role(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    with Session() as s:
        manager=s.query(User).filter_by(username='manager').one()
        # Explicitly remove manager permissions to prove role name is not an authorization bypass.
        manager.role.permissions.clear(); s.commit(); s.refresh(manager)
    with CurrentUserContext(manager):
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_all(*svc.next_month(date(2026,8,31)))


def test_close_month_requires_no_draft_blocks_and_closes_period(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    y,m=svc.next_month(date(2026,8,31))
    with CurrentUserContext(u):
        svc.create(emp.id,date(y,m,3),time(9),time(12),'WORK')
    with Session() as s: manager=s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager):
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.close_month(y,m)
    with CurrentUserContext(u): svc.submit_month(emp.id,y,m)
    with CurrentUserContext(manager):
        assert svc.close_month(y,m)==1
        period=svc.get_period(y,m,manager)
        assert period.status == 'CLOSED'


def test_closed_period_blocks_new_registration(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    y,m=svc.next_month(date(2026,8,31))
    with CurrentUserContext(u): svc.create(emp.id,date(y,m,3),time(9),time(12),'WORK')
    with Session() as s: manager=s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(u): svc.submit_month(emp.id,y,m)
    with CurrentUserContext(manager): svc.close_month(y,m)
    with CurrentUserContext(u):
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id,date(y,m,4),time(13),time(17),'WORK')


def test_audit_records_submission_and_period_close(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    y,m=svc.next_month(date(2026,8,31))
    with CurrentUserContext(u):
        svc.create(emp.id,date(y,m,5),time(9),time(12),'WORK')
        svc.submit_month(emp.id,y,m)
    with Session() as s: manager=s.query(User).filter_by(username='manager').one()
    with CurrentUserContext(manager): svc.close_month(y,m)
    with Session() as s:
        actions=[row.action for row in s.query(__import__('centermanager.models.audit_log',fromlist=['AuditLog']).AuditLog).all()]
    assert 'WORK_REGISTRATION_CREATED' in actions
    assert 'WORK_REGISTRATION_SUBMITTED' in actions
    assert 'WORK_REGISTRATION_PERIOD_CLOSED' in actions

def test_manager_list_all_keeps_employee_relationship_loaded_after_service_session_closes(tmp_path):
    """Management UI consumes detached rows, so employee must be eagerly loaded."""
    Session,u,u2,emp,other=setup_db(tmp_path)
    svc=EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        y,m=svc.next_month(date(2026,8,31))
        svc.create(emp.id,date(y,m,5),time(9),time(12),'WORK')
        svc.submit_month(emp.id,y,m)

    with Session() as s:
        manager=s.query(User).filter_by(username='manager').one()

    with CurrentUserContext(manager):
        rows=svc.list_all(y,m)

    assert len(rows) == 1
    # The service session is already closed here. This must not issue a lazy
    # SELECT against a detached EmployeeWorkRegistration instance.
    assert rows[0].employee is not None
    assert rows[0].employee.employee_code == emp.employee_code
