"""Additional regression contract for the existing Student Timeline renderer."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WIDGET = ROOT / "src" / "centermanager" / "ui" / "timeline" / "timeline_widget.py"
CARD = ROOT / "src" / "centermanager" / "ui" / "timeline" / "timeline_card.py"


def _class(source, name):
    tree = ast.parse(source)
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def _method(node, name):
    return next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def test_timeline_empty_state_is_explicit():
    source = WIDGET.read_text(encoding="utf-8")
    cls = _class(source, "TimelineWidget")
    set_events = ast.unparse(_method(cls, "set_events"))
    empty = ast.unparse(_method(cls, "_show_empty"))
    assert "if not events" in set_events
    assert "_show_empty" in set_events
    assert "No activity yet" in empty


def test_timeline_card_preserves_event_metadata_and_time_display():
    source = CARD.read_text(encoding="utf-8")
    cls = _class(source, "TimelineCard")
    setup = ast.unparse(_method(cls, "_setup_ui"))
    formatter = ast.unparse(_method(cls, "_format_time"))
    assert "_event.event_type" in setup
    assert "_event.created_at" in setup
    assert "Today" in formatter
    assert "Yesterday" in formatter
