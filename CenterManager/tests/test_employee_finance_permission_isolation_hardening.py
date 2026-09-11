from pathlib import Path
import ast

from centermanager.services.employee_document_service import EmployeeDocumentService
from centermanager.models.employee_document import EmployeeDocument
from sqlalchemy.orm import sessionmaker


def _source(path):
    return Path(path).read_text(encoding="utf-8")


def test_finance_pages_have_no_constructor_data_refresh():
    root = Path(__file__).parents[1]
    files = [
        root / "src/centermanager/ui/finance_workspace/finance_dashboard_page.py",
        root / "src/centermanager/ui/finance_workspace/income_list_page.py",
        root / "src/centermanager/ui/finance_workspace/expense_list_page.py",
        root / "src/centermanager/ui/finance_workspace/outstanding_list_page.py",
    ]
    for path in files:
        tree = ast.parse(_source(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                body = ast.get_source_segment(_source(path), node) or ""
                assert ".refresh()" not in body, f"{path.name} performs refresh in __init__"
                assert "QTimer" not in body, f"{path.name} schedules protected work in __init__"


def test_finance_shell_authorization_precedes_dashboard_load():
    root = Path(__file__).parents[1]
    text = _source(root / "src/centermanager/ui/finance_workspace/finance_workspace_shell.py")
    assert "self._authorized = self._has_finance_access()" in text
    # Unauthorized construction must not navigate to a protected page.
    assert 'if self._authorized:\n            self.navigate_to("dashboard")' in text


def test_employee_attachment_publish_mirror_is_recoverable(tmp_path):
    runtime = tmp_path / "runtime"
    repo = runtime / "repository"
    runtime_employee = runtime / "Attachments" / "Employees" / "EMP-00001" / "CV"
    runtime_employee.mkdir(parents=True)
    source = runtime_employee / "cv.pdf"
    source.write_bytes(b"cv-v1")

    # Exercise the same provider mirror logic without requiring a remote.
    import pytest
    pytest.importorskip("PySide6")
    from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider
    provider = GitSynchronizationProvider.__new__(GitSynchronizationProvider)
    provider._repo_path = repo
    provider._repo_path.mkdir(parents=True)
    provider._repo_path.parent.mkdir(parents=True, exist_ok=True)
    provider._repo_path.parent  # runtime
    provider._repo_path = repo
    provider._sync_employee_attachments_to_repository()

    mirrored = repo / "Attachments" / "Employees" / "EMP-00001" / "CV" / "cv.pdf"
    assert mirrored.read_bytes() == b"cv-v1"

    # Replacement/deletion must be reflected exactly on the next publish.
    source.unlink()
    provider._sync_employee_attachments_to_repository()
    assert not mirrored.exists()


def test_employee_document_sync_status_requires_identical_bytes(tmp_path):
    runtime = tmp_path / "runtime"
    attachments = runtime / "Attachments"
    service = EmployeeDocumentService(sessionmaker(), attachments)
    doc = EmployeeDocument(
        relative_path="Attachments/Employees/EMP-00001/CV/cv.pdf",
        original_filename="cv.pdf",
        employee_id=1,
    )
    runtime_path = service.resolve_document_path(doc)
    repo_path = service.document_sync_locations(doc)["repository_path"]
    runtime_path.parent.mkdir(parents=True)
    repo_path.parent.mkdir(parents=True)
    runtime_path.write_bytes(b"v1")
    repo_path.write_bytes(b"v2")
    assert service.verify_repository_sync(doc)["synced"] is False
