"""EP-ARCH-03.32 — SessionNoteService RepositoryProvider boundary regression."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "session_note_service.py"


def test_session_note_service_uses_repository_provider_boundary():
    source = SERVICE.read_text(encoding="utf-8")

    assert "from centermanager.repositories.session_note_repository import SessionNoteRepository" not in source
    assert "RepositoryProvider" in source
    assert "create_default_repository_provider" in source
    assert "self._repository_provider.session_notes(db_session)" in source
    assert "SessionNoteRepository(db_session)" not in source


def test_session_note_service_has_no_direct_session_persistence_operations():
    source = SERVICE.read_text(encoding="utf-8")

    for operation in (
        "db_session.query",
        "db_session.get",
        "db_session.add",
        "db_session.delete",
        "db_session.refresh",
    ):
        assert operation not in source, operation


def test_session_note_service_keeps_existing_constructor_compatibility():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session_service: SessionService" in source
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or create_default_repository_provider()" in source
