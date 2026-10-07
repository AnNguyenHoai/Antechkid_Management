from pathlib import Path
from types import SimpleNamespace

from centermanager.core.current_user import clear_current_user, set_current_user
from centermanager.services.timeline_actor import resolve_timeline_actor


ROOT = Path("src/centermanager")


def test_timeline_actor_defaults_to_authenticated_username():
    set_current_user(SimpleNamespace(username="editor_a"))
    try:
        assert resolve_timeline_actor() == "editor_a"
    finally:
        clear_current_user()


def test_explicit_system_actor_is_never_rewritten_to_logged_in_user():
    set_current_user(SimpleNamespace(username="editor_a"))
    try:
        assert resolve_timeline_actor("system") == "system"
    finally:
        clear_current_user()


def test_no_authenticated_user_falls_back_to_system():
    clear_current_user()
    assert resolve_timeline_actor() == "system"


def test_all_timeline_services_use_canonical_actor_resolver():
    for rel in (
        "services/timeline_service.py",
        "services/class_timeline_service.py",
        "services/teacher_timeline_service.py",
        "services/expense_timeline_service.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "resolve_timeline_actor" in source
        assert "created_by=resolve_timeline_actor(created_by)" in source


def test_timeline_cards_render_created_by_actor():
    for rel in (
        "ui/timeline/timeline_card.py",
        "ui/shared/timeline_card.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert 'getattr(self._event, "created_by", None)' in source
        assert 'QLabel(f"By {actor_name}")' in source


def test_expense_mutations_have_atomic_audit_parity_with_income():
    source = (ROOT / "services/expense_service.py").read_text(encoding="utf-8")

    assert "AuditService" in source
    assert "def _record_audit(" in source
    assert 'module="finance"' in source
    assert 'entity_type="Expense"' in source
    assert 'actor=get_current_user()' in source
    for action in ("CREATE", "UPDATE", "DELETE"):
        assert f'"{action}"' in source


def test_class_fee_history_records_forward_going_editor_without_backfill_guessing():
    model = (ROOT / "models/class_fee_history.py").read_text(encoding="utf-8")
    repo = (ROOT / "repositories/class_repository.py").read_text(encoding="utf-8")
    service = (ROOT / "services/class_service.py").read_text(encoding="utf-8")
    migration = Path("migrations/versions/1e10a039_class_fee_history_actor.py").read_text(encoding="utf-8")

    assert "changed_by" in model
    assert "changed_by=changed_by" in repo
    assert "changed_by=resolve_timeline_actor()" in service
    assert 'op.add_column("class_fee_history"' in migration
    assert "UPDATE class_fee_history" not in migration


def test_existing_explicit_system_highlight_projection_remains_explicit():
    source = (ROOT / "events/handlers/highlight_timeline_handler.py").read_text(encoding="utf-8")
    assert 'created_by="system"' in source
