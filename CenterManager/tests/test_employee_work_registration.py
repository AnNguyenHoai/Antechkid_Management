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
        svc.submit(r.id)
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id,date(2026,8,31),time(9),time(12),'WORK')
        with pytest.raises(EmployeeWorkRegistrationValidationError): svc.create(emp.id,date(y,m,3),time(11),time(13),'WORK')


def test_registration_is_own_employee_only(tmp_path):
    Session,u,u2,emp,other=setup_db(tmp_path); svc=EmployeeWorkRegistrationService(Session)
    with CurrentUserContext(u):
        with pytest.raises(EmployeeWorkRegistrationAccessDeniedError): svc.list_for_employee(other.id,*svc.next_month(date(2026,8,31)))
