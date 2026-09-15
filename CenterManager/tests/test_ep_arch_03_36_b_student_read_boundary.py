"""EP-ARCH-03.36-B — Student read/presentation service boundary contract."""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"

TARGETS = {
    "student_analytics_service.py",
    "student_dashboard_service.py",
    "student_summary_service.py",
}


@pytest.mark.parametrize("service_name", sorted(TARGETS))
def test_student_read_service_declares_repository_provider(service_name: str):
    source = (SERVICES_DIR / service_name).read_text(encoding="utf-8")
    assert "centermanager.repositories.provider" in source
    assert "RepositoryProvider" in source
    assert "SqlAlchemyRepositoryProvider" in source


@pytest.mark.parametrize("service_name", sorted(TARGETS))
def test_student_read_service_has_no_concrete_repository_import(service_name: str):
    source = (SERVICES_DIR / service_name).read_text(encoding="utf-8")
    assert "from centermanager.repositories." not in "\n".join(
        line for line in source.splitlines()
        if "repositories.provider" not in line
    )


@pytest.mark.parametrize("service_name", sorted(TARGETS))
def test_student_read_service_has_no_direct_session_persistence(service_name: str):
    source = (SERVICES_DIR / service_name).read_text(encoding="utf-8")
    forbidden = (
        "session.query(", "session.get(", "session.add(",
        "session.add_all(", "session.delete(", "session.execute(",
        "session.merge(", "session.flush(", "session.refresh(",
    )
    for operation in forbidden:
        assert operation not in source, f"{service_name} contains {operation}"


def test_student_summary_uses_provider_for_document_reads():
    source = (SERVICES_DIR / "student_summary_service.py").read_text(encoding="utf-8")
    assert "self._repository_provider.documents(session)" in source


def test_student_analytics_uses_provider_for_student_and_assessment_reads():
    source = (SERVICES_DIR / "student_analytics_service.py").read_text(encoding="utf-8")
    assert "self._repository_provider.students(session)" in source
    assert "self._repository_provider.assessments(session)" in source


def test_student_dashboard_uses_provider_for_dashboard_reads():
    source = (SERVICES_DIR / "student_dashboard_service.py").read_text(encoding="utf-8")
    for factory in ("students", "assessments", "parents", "sessions", "class_timeline"):
        assert f"self._repository_provider.{factory}(session)" in source
