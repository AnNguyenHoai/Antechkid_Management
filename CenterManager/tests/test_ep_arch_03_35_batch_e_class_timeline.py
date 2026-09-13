from pathlib import Path


SERVICE = Path(__file__).parents[1] / "src" / "centermanager" / "services" / "class_timeline_service.py"


def test_class_timeline_uses_repository_provider():
    source = SERVICE.read_text(encoding="utf-8")
    assert "RepositoryProvider" in source
    assert "self._repository_provider.class_timeline(session)" in source


def test_class_timeline_does_not_refresh_through_session():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.refresh(" not in source
    assert "repo.refresh(event)" in source


def test_class_timeline_keeps_transaction_ownership_in_service():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.commit()" in source
