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


def test_employee_document_sync_requires_matching_file_contents(tmp_path):
    runtime = tmp_path / "runtime"
    attachments = runtime / "Attachments"
    service = EmployeeDocumentService(sessionmaker(), attachments)
    doc = EmployeeDocument(
        relative_path="Attachments/Employees/EMP-00001/CV/test.docx",
        original_filename="test.docx",
        employee_id=1,
    )
    runtime_path = service.resolve_document_path(doc)
    repository_path = service.document_sync_locations(doc)["repository_path"]
    runtime_path.parent.mkdir(parents=True)
    repository_path.parent.mkdir(parents=True)
    runtime_path.write_bytes(b"same-content")
    repository_path.write_bytes(b"different-content")

    locations = service.verify_repository_sync(doc)
    assert locations["runtime_exists"] is True
    assert locations["repository_exists"] is True
    assert locations["checksum_match"] is False
    assert locations["synced"] is False

    repository_path.write_bytes(b"same-content")
    locations = service.verify_repository_sync(doc)
    assert locations["checksum_match"] is True
    assert locations["synced"] is True
