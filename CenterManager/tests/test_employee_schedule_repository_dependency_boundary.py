import inspect

from centermanager.repositories.provider import SqlAlchemyRepositoryProvider
from centermanager.services.employee_schedule_service import EmployeeScheduleService


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


class _Session:
    pass


class _EmployeeRepository:
    def __init__(self, employee):
        self.employee = employee

    def get_by_id(self, employee_id):
        return self.employee


class _ScheduleRepository:
    def list_rules(self, employee_id):
        return []

    def list_exceptions(self, employee_id):
        return []

    def get_rule(self, rule_id):
        return None

    def get_exception(self, exception_id):
        return None


class _Provider:
    def __init__(self, employee):
        self.employee = employee
        self.employee_sessions = []
        self.schedule_sessions = []

    def employees(self, session):
        self.employee_sessions.append(session)
        return _EmployeeRepository(self.employee)

    def employee_schedules(self, session):
        self.schedule_sessions.append(session)
        return _ScheduleRepository()


def test_employee_schedule_service_does_not_select_concrete_repository_implementations():
    source = inspect.getsource(EmployeeScheduleService)

    assert "from centermanager.repositories.employee_repository" not in source
    assert "from centermanager.repositories.employee_schedule_repository" not in source
    assert "EmployeeRepository(" not in source
    assert "EmployeeScheduleRepository(" not in source


def test_employee_lookup_uses_injected_repository_provider():
    employee = type("EmployeeRecord", (), {"user_id": 7})()
    session = _Session()
    provider = _Provider(employee)
    service = EmployeeScheduleService(
        session_factory=lambda: _SessionContext(session),
        repository_provider=provider,
    )

    result = service._employee(123)

    assert result is employee
    assert provider.employee_sessions == [session]


def test_schedule_reads_use_the_injected_schedule_repository():
    employee = type("EmployeeRecord", (), {"user_id": 7})()
    session = _Session()
    provider = _Provider(employee)
    service = EmployeeScheduleService(
        session_factory=lambda: _SessionContext(session),
        repository_provider=provider,
    )

    assert service.list_rules(123, user=type("User", (), {"id": 7})()) == []
    assert service.list_exceptions(123, user=type("User", (), {"id": 7})()) == []
    assert provider.schedule_sessions == [session, session]


def test_production_provider_exposes_employee_schedule_seams():
    provider = SqlAlchemyRepositoryProvider()
    assert callable(provider.employees)
    assert callable(provider.employee_schedules)
