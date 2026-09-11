from pathlib import Path
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.models.employee_document import EmployeeDocument
from centermanager.services.employee_document_service import EmployeeDocumentService


def test_employee_document_resolves_runtime_relative_path(tmp_path):
    runtime = tmp_path / "runtime"
    attachments = runtime / "Attachments"
    service = EmployeeDocumentService(sessionmaker(), attachments)
    doc = EmployeeDocument(relative_path="Attachments/Employees/EMP-00001/CV/test.docx", original_filename="test.docx", employee_id=1)
    assert service.resolve_document_path(doc) == (runtime / "Attachments/Employees/EMP-00001/CV/test.docx").resolve()


def test_employee_document_rejects_path_traversal(tmp_path):
    runtime = tmp_path / "runtime"
    attachments = runtime / "Attachments"
    service = EmployeeDocumentService(sessionmaker(), attachments)
    doc = EmployeeDocument(relative_path="Attachments/../secret.docx", original_filename="secret.docx", employee_id=1)
    try:
        service.resolve_document_path(doc)
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("Path traversal must be rejected")
