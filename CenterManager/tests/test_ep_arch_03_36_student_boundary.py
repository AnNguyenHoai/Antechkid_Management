from pathlib import Path

from centermanager.services.student_export_service import StudentExportService
from centermanager.services.student_import_service import StudentImportService
from centermanager.services.student_note_service import StudentNoteService


def test_student_036_services_declare_repository_provider():
    service_sources = {
        "student_export_service.py": StudentExportService,
        "student_import_service.py": StudentImportService,
        "student_note_service.py": StudentNoteService,
    }
    for filename, service_type in service_sources.items():
        assert "repository_provider" in service_type.__init__.__annotations__, filename


def test_student_036_service_source_has_no_forbidden_direct_session_operations():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"
    for filename in (
        "student_export_service.py",
        "student_import_service.py",
        "student_note_service.py",
    ):
        source = (root / filename).read_text(encoding="utf-8")
        assert "SqlAlchemyRepositoryProvider" not in source, filename
        assert "session.query(" not in source, filename
        assert "session.get(" not in source, filename
        assert "session.add(" not in source, filename
        assert "session.delete(" not in source, filename
