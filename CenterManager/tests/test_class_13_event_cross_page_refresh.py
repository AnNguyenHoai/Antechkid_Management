from pathlib import Path

CLASS_EVENTS = Path("src/centermanager/events/class_events.py").read_text(encoding="utf-8")
CLASS_SERVICE = Path("src/centermanager/services/class_service.py").read_text(encoding="utf-8")
SESSION_SERVICE = Path("src/centermanager/services/session_service.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/class_workspace/class_workspace_shell.py").read_text(encoding="utf-8")
APP = Path("src/centermanager/app.py").read_text(encoding="utf-8")


def test_class_domain_event_contract_exists():
    for name in (
        "ClassCreated",
        "ClassUpdated",
        "ClassArchived",
        "ClassRestored",
        "ClassSessionChanged",
    ):
        assert f"class {name}" in CLASS_EVENTS


def test_class_service_publishes_committed_lifecycle_events():
    for name in ("ClassCreated(", "ClassUpdated(", "ClassArchived(", "ClassRestored("):
        assert name in CLASS_SERVICE
    assert "event_bus: Optional[EventBus] = None" in CLASS_SERVICE


def test_session_service_publishes_class_session_events():
    assert "event_bus: Optional[EventBus] = None" in SESSION_SERVICE
    assert 'action="created"' in SESSION_SERVICE
    assert 'action="updated"' in SESSION_SERVICE
    assert 'action="deleted"' in SESSION_SERVICE


def test_shell_refreshes_from_class_cross_domain_events():
    for name in (
        "ClassCreated",
        "ClassUpdated",
        "ClassArchived",
        "ClassRestored",
        "ClassSessionChanged",
        "StudentEnrollmentChanged",
        "TeacherAssignmentChanged",
    ):
        assert name in SHELL
    assert "def _refresh_for_domain_change" in SHELL
    assert "self.list_page.refresh()" in SHELL
    assert "self.dashboard_page.refresh()" in SHELL


def test_app_uses_shared_event_bus_for_class_and_session_services():
    assert "SessionService(session_factory, event_bus=event_bus)" in APP
    assert "ClassService(session_factory, timeline_service=class_timeline_service, event_bus=event_bus)" in APP
