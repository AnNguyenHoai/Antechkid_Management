"""EP-ARCH-03.19 - RepositoryProvider completeness and lifecycle contract.

The provider is the application-facing repository construction seam. This test
keeps its public factory surface synchronized with the concrete SQLAlchemy
implementation and verifies that repository instances are session-scoped and
not cached across calls.
"""
from __future__ import annotations

import inspect

from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider


EXPECTED_FACTORIES = {
    "audit_logs",
    "class_timeline",
    "attendance",
    "enrollments",
    "sessions",
    "employees",
    "employee_schedules",
    "employee_work_registration_periods",
    "employee_work_registrations",
    "employee_documents",
    "classes",
    "students",
    "assessments",
    "reports",
    "expense_timeline",
    "incomes",
    "teachers",
    "teacher_assignments",
    "teacher_documents",
    "notes",
}


def _public_factory_names(provider_type: type) -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(provider_type, predicate=inspect.isfunction)
        if not name.startswith("_")
        and name not in {"mro"}
        and len(inspect.signature(member).parameters) == 1
    }


def test_repository_provider_protocol_and_implementation_are_complete():
    protocol = _public_factory_names(RepositoryProvider)
    implementation = _public_factory_names(SqlAlchemyRepositoryProvider)

    assert protocol == EXPECTED_FACTORIES
    assert implementation == EXPECTED_FACTORIES
    assert protocol == implementation


def test_repository_provider_factories_are_session_scoped_and_not_cached():
    provider = SqlAlchemyRepositoryProvider()
    session_a = object()
    session_b = object()

    for factory_name in sorted(EXPECTED_FACTORIES):
        factory = getattr(provider, factory_name)

        first = factory(session_a)
        second = factory(session_a)
        other_session = factory(session_b)

        assert first is not second, f"{factory_name} returned a cached repository instance"
        assert other_session is not first, f"{factory_name} reused repository across sessions"
        assert first._session is session_a
        assert second._session is session_a
        assert other_session._session is session_b


def test_repository_provider_factories_have_single_session_parameter():
    provider_methods = {
        name: getattr(SqlAlchemyRepositoryProvider, name)
        for name in EXPECTED_FACTORIES
    }

    for name, method in provider_methods.items():
        parameters = list(inspect.signature(method).parameters.values())
        assert len(parameters) == 2, f"{name} must accept self and session"
        assert parameters[1].name == "session"
