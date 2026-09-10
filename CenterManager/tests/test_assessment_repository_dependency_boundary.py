from pathlib import Path

import pytest

from centermanager.services.assessment_service import AssessmentService
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider


SERVICE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "services"
    / "assessment_service.py"
)


def test_assessment_service_does_not_import_concrete_repository():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "centermanager.repositories.assessment_repository" not in source
    assert "AssessmentRepository(" not in source


def test_repository_provider_exposes_assessments_seam():
    assert hasattr(RepositoryProvider, "assessments")
    assert hasattr(SqlAlchemyRepositoryProvider, "assessments")


def test_assessment_service_uses_injected_repository_provider():
    class FakeRepository:
        def add(self, entity):
            entity.id = 42

    class FakeProvider:
        def __init__(self):
            self.calls = []

        def assessments(self, session):
            self.calls.append(session)
            return FakeRepository()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def commit(self):
            pass

        def refresh(self, entity):
            pass

    class FakeFactory:
        def __call__(self):
            return FakeSession()

    provider = FakeProvider()
    service = AssessmentService(FakeFactory(), repository_provider=provider)

    result = service.create_assessment(
        student_id=7,
        assessment_date=__import__("datetime").date(2026, 9, 10),
        assessment_type="MONTHLY",
        strengths="Good",
        improvements="Practice",
        next_goal="Next",
    )

    assert result.id == 42
    assert len(provider.calls) == 1
