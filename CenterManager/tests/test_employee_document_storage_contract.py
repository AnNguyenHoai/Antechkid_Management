from pathlib import Path
from sqlalchemy.orm import sessionmaker

from centermanager.models.employee_document import EmployeeDocument
from centermanager.services.employee_document_service import EmployeeDocumentService


def test_employee_document_storage_has_runtime_and_repository_locations(tmp_path):
    runtime = tmp_path / "runtime"
    attachments = runtime / "Attachments"
    service = EmployeeDocumentService(sessionmaker(), attachments)

    doc = EmployeeDocument(
        relative_path="Attachments/Employees/EMP-00001/CV/test.docx",
        original_filename="test.docx",
        employee_id=1,
    )

    locations = service.document_sync_locations(doc)

    assert locations["runtime_path"] == (
        runtime / "Attachments/Employees/EMP-00001/CV/test.docx"
    ).resolve()
    assert locations["repository_path"] == (
        runtime / "repository/Attachments/Employees/EMP-00001/CV/test.docx"
    ).resolve()
    assert locations["runtime_exists"] is False
    assert locations["repository_exists"] is False
    assert locations["synced"] is False


def test_employee_document_repository_path_cannot_be_absolute(tmp_path):
    runtime = tmp_path / "runtime"
    service = EmployeeDocumentService(sessionmaker(), runtime / "Attachments")
    doc = EmployeeDocument(
        relative_path=str((tmp_path / "outside.docx").resolve()),
        original_filename="outside.docx",
        employee_id=1,
    )
    try:
        service.get_repository_relative_path(doc)
    except ValueError as exc:
        assert "relative" in str(exc).lower()
    else:
        raise AssertionError("Absolute document paths must be rejected")
