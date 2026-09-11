from datetime import date, time
from types import SimpleNamespace

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_working_time_service import EmployeeWorkingTimeService


class _FakeWorkingRepo:
    def __init__(self, rows):
        self.rows = rows

    def list_for_employee(self, employee_id, start_date=None, end_date=None):
        return list(self.rows)


class _FakeEmployeeRepo:
    def __init__(self, employee):
        self.employee = employee

    def get_by_id(self, employee_id):
        return self.employee


def _user(user_id=10, permissions=(), role=RoleDefinitions.TEACHER):
    return SimpleNamespace(
        id=user_id,
        role=SimpleNamespace(name=role),
        permissions=set(permissions),
    )


def test_monthly_summary_uses_schedule_with_same_authorization_context(monkeypatch):
    employee = SimpleNamespace(id=20, user_id=99)
    actor = _user(
        permissions={
            PermissionDefinitions.WORKING_TIME_VIEW_ALL,
            PermissionDefinitions.SCHEDULE_VIEW_ALL,
        }
    )

    class _Session:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "centermanager.services.employee_working_time_service.EmployeeRepository",
        lambda session: _FakeEmployeeRepo(employee),
    )
    monkeypatch.setattr(
        "centermanager.services.employee_working_time_service.EmployeeWorkingTimeRepository",
        lambda session: _FakeWorkingRepo([]),
    )

    class _Schedule:
        def __init__(self):
            self.calls = []
        def expected_for_date(self, employee_id, work_date, user=None):
            self.calls.append((employee_id, work_date, user))
            return [(time(9, 0), time(17, 0))]

    schedule = _Schedule()
    service = EmployeeWorkingTimeService(lambda: _Session(), schedule_service=schedule)
    result = service.monthly_summary(employee.id, 2026, 1, actor)

    assert result["expected_minutes"] == 8 * 60 * 31
    assert len(schedule.calls) == 31
    assert all(call[2] is actor for call in schedule.calls)
