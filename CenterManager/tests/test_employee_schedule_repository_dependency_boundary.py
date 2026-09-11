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
    def commit(self):
        pass


class _EmployeeRepository:
    def __init__(self, employee):
        self.employee = employee

    def get_by_id(self, employee_id):
        return self.employee


class _ScheduleRepository:
    def __init__(self):
        self.added_rules = []
        self.updated_rules = []
        self.deleted_rules = []
        self.added_exceptions = []
        self.deleted_exceptions = []

    def list_rules(self, employee_id):
        return []

    def list_exceptions(self, employee_id):
        return []

    def get_rule(self, rule_id):
        return None

    def get_exception(self, exception_id):
        return None

    def add_rule(self, rule):
        self.added_rules.append(rule)
        return rule

    def update_rule(self, rule, **kwargs):
        self.updated_rules.append((rule, kwargs))
        return rule

    def delete_rule(self, rule):
        self.deleted_rules.append(rule)

    def add_exception(self, exception):
        self.added_exceptions.append(exception)
        return exception

    def delete_exception(self, exception):
        self.deleted_exceptions.append(exception)


class _Provider:
    def __init__(self, employee):
        self.employee = employee
        self.employee_sessions = []
        self.schedule_sessions = []
        self.schedule_repo = _ScheduleRepository()

    def employees(self, session):
        self.employee_sessions.append(session)
        return _EmployeeRepository(self.employee)

    def employee_schedules(self, session):
        self.schedule_sessions.append(session)
        return self.schedule_repo


def _self_schedule_user(user_id=7):
    role = type("Role", (), {"name": "employee"})()
    return type(
        "User",
        (),
        {"id": user_id, "role": role, "permissions": {"schedule.view.self"}},
    )()


def test_employee_schedule_service_does_not_select_concrete_repository_implementations():
    source = inspect.getsource(EmployeeScheduleService)

    assert "from centermanager.repositories.employee_repository" not in source
    assert "from centermanager.repositories.employee_schedule_repository" not in source
    assert "EmployeeRepository(" not in source
    assert "EmployeeScheduleRepository(" not in source
    assert "SqlAlchemyRepositoryProvider(" not in source


def test_employee_schedule_service_uses_provider_default_factory():
    source = inspect.getsource(EmployeeScheduleService)
    assert "create_default_repository_provider" in source


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
    user = _self_schedule_user()

    assert service.list_rules(123, user=user) == []
    assert service.list_exceptions(123, user=user) == []
    assert provider.schedule_sessions == [session, session]


def test_schedule_mutations_delegate_persistence_to_repository():
    employee = type("EmployeeRecord", (), {"user_id": 7})()
    session = _Session()
    provider = _Provider(employee)
    service = EmployeeScheduleService(
        session_factory=lambda: _SessionContext(session),
        repository_provider=provider,
    )
    user = type(
        "Manager",
        (),
        {"id": 1, "role": type("Role", (), {"name": "manager"})(), "permissions": {"schedule.manage"}},
    )()

    rule = service.add_rule(123, 0, __import__("datetime").time(9), __import__("datetime").time(10), __import__("datetime").date(2040, 1, 1), user=user)
    assert provider.schedule_repo.added_rules == [rule]

    service.delete_rule(99, user=user)  # missing rule remains a no-op
    assert provider.schedule_repo.deleted_rules == []


def test_production_provider_exposes_employee_schedule_seams():
    provider = SqlAlchemyRepositoryProvider()
    assert callable(provider.employees)
    assert callable(provider.employee_schedules)
