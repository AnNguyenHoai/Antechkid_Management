"""EP-ARCH-03.31 — ParentService RepositoryProvider boundary regression."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "parent_service.py"


def test_parent_service_uses_repository_provider_boundary():
    source = SERVICE.read_text(encoding="utf-8")

    assert "from centermanager.repositories.parent_repository import ParentRepository" not in source
    assert "RepositoryProvider" in source
    assert "create_default_repository_provider" in source
    assert "self._repository_provider.parents(session)" in source
    assert "ParentRepository(session)" not in source


def test_parent_service_has_no_direct_session_persistence_operations():
    source = SERVICE.read_text(encoding="utf-8")

    for operation in ("session.query", "session.get", "session.add", "session.delete", "session.refresh"):
        assert operation not in source, operation


def test_parent_service_constructor_keeps_existing_dependencies_compatible():
    source = SERVICE.read_text(encoding="utf-8")
    assert "timeline_service: Optional[TimelineService] = None" in source
    assert "event_bus: Optional[EventBus] = None" in source
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
