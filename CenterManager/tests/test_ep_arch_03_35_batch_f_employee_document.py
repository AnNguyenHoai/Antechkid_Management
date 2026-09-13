from pathlib import Path


SERVICE_PATH = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services" / "employee_document_service.py"
INVENTORY_PATH = Path(__file__).resolve().parents[1] / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_employee_document_service_uses_repository_provider_for_persistence():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "RepositoryProvider" in source
    assert "self._repository_provider.employee_documents(s)" in source
    assert "repo.add(d)" in source
    assert "repo.refresh(d)" in source
    assert "session.query(" not in source
    assert "session.add(" not in source
    assert "session.delete(" not in source
    assert "session.refresh(" not in source


def test_inventory_promotes_employee_document_service():
    source = INVENTORY_PATH.read_text(encoding="utf-8")
    assert "`employee_document_service.py` | PASS" in source
    assert "EmployeeDocumentService" in source
    assert "RepositoryProvider.employee_documents(...)" in source
