"""EP-ARCH-03.37 — SessionService/TimelineService repository-boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def _service(name: str) -> str:
    return (SERVICES / name).read_text(encoding="utf-8")


def test_session_and_timeline_services_use_repository_provider_boundary():
    session = _service("session_service.py")
    timeline = _service("timeline_service.py")

    assert "RepositoryProvider" in session
    assert "centermanager.repositories.session_repository" not in session
    assert "centermanager.repositories.class_repository" not in session
    assert "SessionRepository(" not in session
    assert "ClassRepository(" not in session
    assert "session.query(" not in session
    assert "session.add(" not in session
    assert "session.delete(" not in session
    assert "session.refresh(" not in session
    assert "repo.refresh(" in session
    assert "_repository_provider.sessions(" in session
    assert "_repository_provider.classes(" in session

    assert "RepositoryProvider" in timeline
    assert "centermanager.repositories.timeline_repository" not in timeline
    assert "TimelineRepository(" not in timeline
    assert "session.query(" not in timeline
    assert "session.add(" not in timeline
    assert "session.delete(" not in timeline
    assert "session.refresh(" not in timeline
    assert "repo.refresh(" in timeline
    assert "_repository_provider.timeline(" in timeline


def test_session_and_timeline_services_are_promoted_to_pass():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in ("session_service.py", "timeline_service.py"):
        row_start = source.index(f"`{service_name}`")
        row = source[row_start : source.index("\n", row_start)]
        assert "| PASS |" in row, row

    assert "EP-ARCH-03.37 Session/Timeline repository boundary" in source
