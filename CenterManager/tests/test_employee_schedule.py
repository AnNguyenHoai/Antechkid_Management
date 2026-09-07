from datetime import date, time
from pathlib import Path
import pytest
from centermanager.models.employee_schedule import EmployeeScheduleRule, EmployeeScheduleException

ROOT=Path(__file__).resolve().parents[1]

def test_schedule_migration_contract():
    p=ROOT/'migrations'/'versions'/'1e10a006_employee_schedule_foundation.py'
    s=p.read_text(encoding='utf-8')
    assert 'revision = "1e10a006"' in s
    assert 'down_revision = "1e10a005"' in s
    assert 'employee_schedule_rules' in s
    assert 'employee_schedule_exceptions' in s
    assert 'schedule.view.self' in s and 'schedule.view.all' in s and 'schedule.manage' in s

def test_rule_model_contract():
    assert EmployeeScheduleRule.__tablename__ == 'employee_schedule_rules'
    assert EmployeeScheduleRule.day_of_week.property.columns[0].nullable is False
    assert EmployeeScheduleRule.effective_from.property.columns[0].nullable is False

def test_exception_model_has_one_per_employee_date():
    constraints=[c for c in EmployeeScheduleException.__table__.constraints if getattr(c,'name',None)=='uq_employee_schedule_exception_date']
    assert constraints
    assert {c.name for c in constraints[0].columns} == {'employee_id','schedule_date'}

from sqlalchemy.orm import sessionmaker
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import User, Role, Employee, Permission
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_service import EmployeeService
from centermanager.services.employee_schedule_service import EmployeeScheduleService, EmployeeScheduleValidationError, EmployeeScheduleAccessDeniedError
from centermanager.core.current_user import CurrentUserContext

def test_schedule_service_rejects_overlap_and_self_write(tmp_path):
    engine=create_engine_for_path(tmp_path/'schedule.db'); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as s:
        mr=Role(name='manager',display_name='Manager',is_system=True); tr=Role(name='teacher',display_name='Teacher',is_system=True)
        schedule_manage=Permission(name='schedule.manage',description='manage',category='employee')
        schedule_view_self=Permission(name='schedule.view.self',description='self',category='employee')
        s.add_all([mr,tr,schedule_manage,schedule_view_self]); s.flush(); tr.permissions.append(schedule_view_self); mr.permissions.append(schedule_manage); s.add_all([mr,tr]); s.flush()
        manager=User(username='manager',password_hash='x',full_name='Manager',role_id=mr.id,is_active=True,force_password_change=False)
        teacher=User(username='teacher',password_hash='x',full_name='Teacher',role_id=tr.id,is_active=True,force_password_change=False);s.add_all([manager,teacher]);s.commit();s.refresh(manager);s.refresh(teacher)
    es=EmployeeService(Session)
    with CurrentUserContext(manager): employee=es.create_employee('Teacher',user_id=teacher.id)
    ss=EmployeeScheduleService(Session)
    with CurrentUserContext(manager):
        ss.add_rule(employee.id,0,time(9),time(12),date(2026,9,1))
        with pytest.raises(EmployeeScheduleValidationError): ss.add_rule(employee.id,0,time(11),time(13),date(2026,9,1))
    with CurrentUserContext(teacher):
        assert ss.list_rules(employee.id)
        with pytest.raises(EmployeeScheduleAccessDeniedError): ss.add_rule(employee.id,1,time(9),time(10),date(2026,9,1))

def test_schedule_manage_allows_read_without_granting_manage_from_view_all():
    engine=create_engine_for_path(tmp_path/'schedule-read.db'); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as s:
        manager_role=Role(name='manager',display_name='Manager',is_system=True)
        teacher_role=Role(name='teacher',display_name='Teacher',is_system=True)
        manage=Permission(name='schedule.manage',description='manage',category='employee')
        view_all=Permission(name='schedule.view.all',description='view all',category='employee')
        view_self=Permission(name='schedule.view.self',description='view self',category='employee')
        s.add_all([manager_role,teacher_role,manage,view_all,view_self]); s.flush()
        manager_role.permissions.append(manage)
        teacher_role.permissions.append(view_all)
        manager=User(username='manager',password_hash='x',full_name='Manager',role_id=manager_role.id,is_active=True,force_password_change=False)
        teacher=User(username='teacher',password_hash='x',full_name='Teacher',role_id=teacher_role.id,is_active=True,force_password_change=False)
        s.add_all([manager,teacher]); s.commit(); s.refresh(manager); s.refresh(teacher)
    es=EmployeeService(Session)
    with CurrentUserContext(manager): employee=es.create_employee('Teacher',user_id=teacher.id)
    ss=EmployeeScheduleService(Session)
    with CurrentUserContext(manager):
        ss.add_rule(employee.id,0,time(9),time(12),date(2026,9,1))
        assert ss.list_rules(employee.id)
    with CurrentUserContext(teacher):
        assert ss.list_rules(employee.id)
        with pytest.raises(EmployeeScheduleAccessDeniedError):
            ss.add_rule(employee.id,1,time(9),time(10),date(2026,9,1))
