"""EP-ARCH-03.36-D — Student filter/highlight repository boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"
SERVICES = SRC / "services"
REPOSITORIES = SRC / "repositories"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def _source(name: str) -> str:
    return (SERVICES / name).read_text(encoding="utf-8")


def test_filter_service_uses_repository_provider_and_not_session_queries():
    source = _source("student_filter_service.py")
    repository_source = (REPOSITORIES / "student_repository.py").read_text(encoding="utf-8")
    assert "RepositoryProvider" in source
    assert "self._repository_provider.students(session)" in source
    assert "session.query" not in source
    assert "StudentRepository" not in source
    assert 'Student.status == "ARCHIVED"' in repository_source


def test_highlight_service_uses_repository_provider_and_not_concrete_repository():
    source = _source("student_highlight_service.py")
    assert "RepositoryProvider" in source
    assert "self._repository_provider.student_highlights(db_session)" in source
    assert "StudentHighlightRepository" not in source
    assert "db_session.refresh" not in source
    assert "repo.add" in source
    assert "repo.delete" in source


def test_inventory_promotes_student_filter_and_highlight_services():
    source = INVENTORY.read_text(encoding="utf-8")
    assert "`student_filter_service.py` | PASS |" in source
    assert "`student_highlight_service.py` | PASS |" in source
    assert "## EP-ARCH-03.36-D Student filter/highlight boundary" in source
    section = source.split("## EP-ARCH-03.36-D Student filter/highlight boundary", 1)[1]
    assert "**StudentFilterService**" in section
    assert "**StudentHighlightService**" in section
    assert "RepositoryProvider.student_highlights(...)" in section
    assert "repository-owned" in section
