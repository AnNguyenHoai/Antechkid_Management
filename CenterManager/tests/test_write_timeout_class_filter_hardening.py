# -*- coding: utf-8 -*-
"""Regression contracts for WRITE idle tracking and Class active-first listing."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_editing_idle_timeout_uses_monotonic_activity_guard():
    main = _source("ui/main_window.py")

    assert "self._last_user_activity_monotonic = time.monotonic()" in main
    assert "elapsed_ms = int(" in main
    assert "if elapsed_ms < self.EDITING_IDLE_TIMEOUT_MS:" in main
    assert "Ignoring stale editing idle timeout callback" in main
    assert "source=IDLE_TIMER" in main
    assert "last_activity_at=%s" in main


def test_editing_activity_tracks_ime_and_real_user_input():
    main = _source("ui/main_window.py")

    assert "def _record_user_activity" in main
    assert "QEvent.Type.KeyPress" in main
    assert "QEvent.Type.MouseButtonPress" in main
    assert "QEvent.Type.MouseButtonDblClick" in main
    assert "QEvent.Type.Wheel" in main
    assert "QEvent.Type.TouchBegin" in main
    assert "QEvent.Type.InputMethod" in main
    assert "QEvent.Type.Shortcut" in main
    assert "self._record_user_activity(event.type().name)" in main


def test_system_refresh_does_not_count_as_user_activity():
    main = _source("ui/main_window.py")
    block = main.split("def _arm_editing_idle_timer", 1)[1].split(
        "def eventFilter", 1
    )[0]

    assert 'self._record_user_activity("editing-state-arm")' not in block
    assert "if not self._editing_idle_timer.isActive():" in block
    assert "self._editing_idle_timer.start(self.EDITING_IDLE_TIMEOUT_MS)" in block


def test_lease_failure_is_observable_as_distinct_from_idle_timeout():
    main = _source("ui/main_window.py")

    assert "source=LEASE_RENEWAL_FAILED" in main
    assert "this was not an inactivity timeout" in main


def test_class_list_defaults_to_active_and_name_sort():
    page = _source("ui/class_workspace/class_list_page.py")

    assert 'self._sort_key: Optional[str] = "name"' in page
    assert '"options": ["Active", "Inactive"]' in page
    assert 'self.search_bar.set_filter_value("status", "Active")' in page
    assert "self.status_filter = status_control" in page


def test_class_search_preserves_selected_status_filter():
    page = _source("ui/class_workspace/class_list_page.py")
    filter_block = page.split("def _filter_classes", 1)[1].split(
        "def _populate_table", 1
    )[0]

    assert 'status_label = self.search_bar.filters().get("status", "")' in filter_block
    assert 'status = status_map.get(status_label, "ALL")' in filter_block
    assert 'if status == "ALL" or (class_obj.status or "ACTIVE") == status' in filter_block
    assert "teacher_names" in filter_block
    assert "self._class_service.search_classes" not in filter_block
