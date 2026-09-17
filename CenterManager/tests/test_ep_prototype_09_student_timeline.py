"""Source-driven regression contract for EP-PROTOTYPE-09."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
STUDENT_DETAIL = ROOT / "src" / "centermanager" / "ui" / "student_workspace" / "student_detail_page.py"
TIMELINE_SERVICE = ROOT / "src" / "centermanager" / "services" / "timeline_service.py"
TIMELINE_WIDGET = ROOT / "src" / "centermanager" / "ui" / "timeline" / "timeline_widget.py"
TIMELINE_CARD = ROOT / "src" / "centermanager" / "ui" / "timeline" / "timeline_card.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_node(source: str, name: str) -> ast.ClassDef:
    tree = ast.parse(source)
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def _method_node(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(
        child for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name
    )


def test_ep_prototype_09_student_detail_exposes_timeline():
    source = _read(STUDENT_DETAIL)
    cls = _class_node(source, "StudentDetailPage")
    setup = _method_node(cls, "_setup_ui")
    profile = _method_node(cls, "_create_profile_tab")
    populate = _method_node(cls, "_populate_profile")

    setup_source = ast.unparse(setup)
    profile_source = ast.unparse(profile)
    populate_source = ast.unparse(populate)

    assert "TimelineWidget" in setup_source or "TimelineWidget" in profile_source
    assert "timeline_section" in profile_source
    assert "Timeline" in profile_source
    assert "get_student_timeline" in populate_source
    assert "timeline_widget.set_events" in populate_source


def test_ep_prototype_09_timeline_service_owns_retrieval_and_persistence():
    source = _read(TIMELINE_SERVICE)
    cls = _class_node(source, "TimelineService")
    log_event = _method_node(cls, "log_event")
    get_timeline = _method_node(cls, "get_student_timeline")

    log_source = ast.unparse(log_event)
    get_source = ast.unparse(get_timeline)

    assert "_session_factory" in log_source
    assert "_repository_provider" in log_source
    assert "repo.add" in log_source
    assert "session.commit" in log_source
    assert "timeline" in get_source.lower()
    assert "repo.get_by_student" in get_source


def test_ep_prototype_09_timeline_widget_is_read_only_renderer():
    source = _read(TIMELINE_WIDGET)
    cls = _class_node(source, "TimelineWidget")
    set_events = _method_node(cls, "set_events")

    set_source = ast.unparse(set_events)
    assert "TimelineCard" in set_source
    assert "set_events" in source
    assert "repo" not in set_source.lower()
    assert "session" not in set_source.lower()


def test_ep_prototype_09_timeline_card_is_read_only_presentation():
    source = _read(TIMELINE_CARD)
    cls = _class_node(source, "TimelineCard")
    setup = _method_node(cls, "_setup_ui")

    setup_source = ast.unparse(setup)
    assert "_event.title" in setup_source
    assert "_event.description" in setup_source
    assert "_event.event_type" in setup_source
    assert "commit" not in setup_source.lower()
    assert "delete" not in setup_source.lower()
    assert "save" not in setup_source.lower()
