"""EP-ARCH-03.36-C — Student document repository boundary contract."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE = PROJECT_ROOT / "src" / "centermanager" / "services" / "student_document_service.py"
INVENTORY = PROJECT_ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_student_document_service_declares_repository_provider():
    source = SERVICE.read_text(encoding="utf-8")
    assert "centermanager.repositories.provider" in source
    assert "RepositoryProvider" in source
    assert "create_default_repository_provider" in source


def test_student_document_service_has_no_concrete_repository_import_or_constructor():
    source = SERVICE.read_text(encoding="utf-8")
    assert "from centermanager.repositories.document_repository import DocumentRepository" not in source
    assert "DocumentRepository(session)" not in source
    assert not any(
        line.strip().startswith("from centermanager.repositories.")
        and "repositories.provider" not in line
        for line in source.splitlines()
    )


def test_student_document_service_uses_provider_for_document_access():
    source = SERVICE.read_text(encoding="utf-8")
    assert "self._repository_provider.documents(session)" in source
    assert source.count("self._repository_provider.documents(session)") == 3


def test_student_document_service_keeps_transaction_and_filesystem_boundaries():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.commit()" in source
    assert "repo.refresh(doc)" in source
    assert "repo.delete(doc)" in source
    assert "shutil.copy2(source_path, dest_path)" in source
    assert "file_path.unlink()" in source
    assert "get_paths().attachment_dir" in source


def test_inventory_promotes_student_document_service():
    source = INVENTORY.read_text(encoding="utf-8")
    row = next(
        line for line in source.splitlines()
        if line.startswith("| `student_document_service.py` |")
    )
    assert "| PASS |" in row
    section = source[source.index("## EP-ARCH-03.36-C Student document boundary"):]
    assert "**StudentDocumentService**" in section
    assert "repository-owned" in section
    assert "filesystem behavior remains service-owned" in section
