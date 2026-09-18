from sqlalchemy.orm import sessionmaker

from centermanager.models.employee_document import EmployeeDocument
from centermanager.services.employee_document_service import EmployeeDocumentService


def test_employee_document_legacy_plural_path_resolves_into_canonical_runtime_root(tmp_path):
    runtime = tmp_path / "runtime"
    # Historical callers supplied the plural runtime root. The service must
    # normalize it to the canonical singular Attachment directory.
    service = EmployeeDocumentService(sessionmaker(), runtime / "Attachments")
    doc = EmployeeDocument(
        relative_path="Attachments/Employees/EMP-00001/CV/test.docx",
        original_filename="test.docx",
        employee_id=1,
    )
    assert service.resolve_document_path(doc) == (
        runtime / "Attachment/Employees/EMP-00001/CV/test.docx"
    ).resolve()


def test_employee_document_canonical_path_maps_to_plural_repository_contract(tmp_path):
    runtime = tmp_path / "runtime"
    service = EmployeeDocumentService(sessionmaker(), runtime / "Attachment")
    doc = EmployeeDocument(
        relative_path="Attachment/Employees/EMP-00001/CV/test.docx",
        original_filename="test.docx",
        employee_id=1,
    )

    assert service.resolve_document_path(doc) == (
        runtime / "Attachment/Employees/EMP-00001/CV/test.docx"
    ).resolve()
    assert service.get_repository_relative_path(doc).as_posix() == (
        "Attachments/Employees/EMP-00001/CV/test.docx"
    )


def test_employee_document_rejects_path_traversal(tmp_path):
    runtime = tmp_path / "runtime"
    service = EmployeeDocumentService(sessionmaker(), runtime / "Attachments")
    doc = EmployeeDocument(
        relative_path="Attachments/../secret.docx",
        original_filename="secret.docx",
        employee_id=1,
    )
    try:
        service.resolve_document_path(doc)
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("Path traversal must be rejected")
