from datetime import date, time, datetime
import pytest
from sqlalchemy.orm import sessionmaker
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models import User, Role, Employee, Permission
from centermanager.services.employee_service import EmployeeService
from centermanager.services.employee_working_time_service import (
    EmployeeWorkingTimeService, EmployeeWorkingTimeValidationError, EmployeeWorkingTimeAccessDeniedError,
)
from centermanager.services.employee_schedule_service import EmployeeScheduleService
from centermanager.core.current_user import CurrentUserContext


def setup_db(tmp_path):
    engine=create_engine_for_path(tmp_path/'working.db'); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as s:
        mr=Role(name='manager',display_name='Manager',is_system=True)
        tr=Role(name='teacher',display_name='Teacher',is_system=True)
        ps=[Permission(name=n,description=n,category='employee') for n in ('working_time.view.self','working_time.view.all','working_time.create.self','working_time.manage','working_time.lock')]
        s.add_all([mr,tr,*ps]); s.flush()
        for p in ps: mr.permissions.append(p)
        for p in ps:
            if p.name in ('working_time.view.self','working_time.create.self'): tr.permissions.append(p)
        manager=User(username='manager',password_hash='x',full_name='Manager',role_id=mr.id,is_active=True,force_password_change=False)
        teacher=User(username='teacher',password_hash='x',full_name='Teacher',role_id=tr.id,is_active=True,force_password_change=False)
        teacher2=User(username='teacher2',password_hash='x',full_name='Teacher 2',role_id=tr.id,is_active=True,force_password_change=False)
        s.add_all([manager,teacher,teacher2]); s.flush(); s.commit(); s.refresh(manager); s.refresh(teacher); s.refresh(teacher2)
    es=EmployeeService(Session)
    with CurrentUserContext(manager): emp=es.create_employee('Teacher',user_id=teacher.id)
    return Session, manager, teacher, teacher2, emp


def test_self_booking_checkin_checkout_and_overlap(tmp_path):
    Session, manager, teacher, teacher2, emp = setup_db(tmp_path)
    svc=EmployeeWorkingTimeService(Session, EmployeeScheduleService(Session))
    with CurrentUserContext(teacher):
        e=svc.create_booking(emp.id,date(2026,9,1),time(9),time(12),'TEACHING')
        assert e.status=='BOOKED'
        with pytest.raises(EmployeeWorkingTimeValidationError):
            svc.create_booking(emp.id,date(2026,9,1),time(11),time(13),'TEACHING')
        opened=svc.check_in(emp.id,datetime(2026,9,2,13,30))
        assert opened.status=='OPEN' and opened.end_time is None
        closed=svc.check_out(opened.id,datetime(2026,9,2,17,30))
        assert closed.status=='BOOKED' and closed.end_time==time(17,30)


def test_self_cannot_access_other_employee_and_manager_can_manage(tmp_path):
    Session, manager, teacher, teacher2, emp = setup_db(tmp_path)
    es=EmployeeService(Session)
    with CurrentUserContext(manager): other=es.create_employee('Other',user_id=teacher2.id)
    svc=EmployeeWorkingTimeService(Session, EmployeeScheduleService(Session))
    with CurrentUserContext(teacher):
        with pytest.raises(EmployeeWorkingTimeAccessDeniedError): svc.list_entries(other.id)
    with CurrentUserContext(manager):
        e=svc.create_booking(other.id,date(2026,9,1),time(9),time(17),'ADMIN')
        assert e.id
        svc.approve(e.id)
        with pytest.raises(EmployeeWorkingTimeAccessDeniedError): svc.update_booking(e.id,work_date=e.work_date,start_time=time(10),end_time=time(17),work_type='ADMIN')


def test_monthly_summary_uses_schedule(tmp_path):
    Session, manager, teacher, teacher2, emp = setup_db(tmp_path)
    schedule=EmployeeScheduleService(Session)
    svc=EmployeeWorkingTimeService(Session, schedule)
    with CurrentUserContext(manager):
        schedule.add_rule(emp.id,0,time(9),time(12),date(2026,9,1))
        svc.create_booking(emp.id,date(2026,9,7),time(9),time(12),'TEACHING')
        summary=svc.monthly_summary(emp.id,2026,9)
        assert summary['actual_minutes']==180
        assert summary['expected_minutes']==720
        assert summary['overtime_minutes']==0
        assert summary['shortfall_minutes']==540


def test_lock_month(tmp_path):
    Session, manager, teacher, teacher2, emp = setup_db(tmp_path)
    svc=EmployeeWorkingTimeService(Session)
    with CurrentUserContext(manager):
        svc.create_booking(emp.id,date(2026,9,1),time(9),time(12),'WORK')
        assert svc.lock_month(emp.id,2026,9)==1
        with pytest.raises(EmployeeWorkingTimeAccessDeniedError):
            svc.delete_entry(1)
