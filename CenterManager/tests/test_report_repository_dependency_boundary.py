from pathlib import Path

from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.services.report_service import ReportService


SERVICE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "services"
    / "report_service.py"
)


def test_report_service_does_not_import_or_construct_concrete_repository():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "centermanager.repositories.report_repository" not in source
    assert "ReportRepository(" not in source


def test_repository_provider_exposes_reports_seam():
    assert hasattr(RepositoryProvider, "reports")
    assert hasattr(SqlAlchemyRepositoryProvider, "reports")


def test_report_service_uses_injected_repository_provider():
    class FakeRepository:
        def __init__(self):
            self.calls = []

        def get_by_student(self, student_id):
            self.calls.append(("get_by_student", student_id))
            return []

        def get_by_student_and_trigger(self, student_id, trigger_event):
            self.calls.append(("get_by_student_and_trigger", student_id, trigger_event))
            return None

        def exists_for_student_trigger_on_date(self, student_id, trigger_event, target_date):
            self.calls.append(("exists_for_student_trigger_on_date", student_id, trigger_event, target_date))
            return False

        def get_by_id(self, report_id):
            self.calls.append(("get_by_id", report_id))
            return None

    class FakeProvider:
        def __init__(self):
            self.repository = FakeRepository()
            self.calls = []

        def reports(self, session):
            self.calls.append(session)
            return self.repository

    class FakeFactory:
        def __call__(self):
            class Session:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False
            return Session()

    provider = FakeProvider()
    service = ReportService(
        student_service=None,
        parent_service=None,
        attendance_service=None,
        session_service=None,
        student_note_service=None,
        outstanding_service=None,
        income_service=None,
        session_factory=FakeFactory(),
        repository_provider=provider,
    )

    assert service.get_student_reports(7) == []
    assert service.report_exists(7, "daily") is False
    assert len(provider.calls) == 2
    assert len(provider.repository.calls) == 2
