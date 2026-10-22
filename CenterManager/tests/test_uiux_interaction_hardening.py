# -*- coding: utf-8 -*-
"""UI/UX interaction hardening contracts.

These tests intentionally protect presentation/accessibility behavior only.
They must not introduce DB, migration, or business-rule dependencies.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_canonical_controls_have_strong_focus_ring():
    foundation = _source("design_system/foundation.py")

    assert 'QPushButton:focus {{' in foundation
    assert 'QLineEdit:focus {{' in foundation
    assert 'QComboBox:focus {{' in foundation
    assert foundation.count('border: 2px solid {COLORS["focus_ring"]};') >= 3


def test_workspace_card_is_keyboard_focusable_and_activates_with_enter_or_space():
    card = _source("home/workspace_card.py")

    assert "setFocusPolicy(Qt.FocusPolicy.StrongFocus)" in card
    assert "QFrame#HomeWorkspaceCard:focus" in card
    assert "def keyPressEvent" in card
    assert "Qt.Key.Key_Return" in card
    assert "Qt.Key.Key_Enter" in card
    assert "Qt.Key.Key_Space" in card
    assert "self.clicked.emit(self._workspace_id)" in card


def test_desktop_polish_covers_native_interaction_surfaces():
    desktop = _source("design_system/desktop.py")

    required = (
        "QMenu::item:selected",
        "QTableView::item:hover",
        "QTableView::item:selected",
        "QTreeView::item:hover",
        "QListView::item:selected",
        "QHeaderView::section",
        "QTabBar::tab:hover",
        "QTabBar::tab:selected",
        "QStatusBar",
        "QScrollBar::handle:vertical:hover",
        "QScrollBar::handle:horizontal:hover",
    )
    for selector in required:
        assert selector in desktop
    assert "border: 2px solid {COLORS['focus_ring']};" in desktop


def test_student_toolbar_clear_is_atomic_and_advanced_filter_is_visible():
    page = _source("student_workspace/student_list_page.py")

    assert "clicked.disconnect(self.search_bar.clear)" in page
    assert "clicked.connect(self._clear_toolbar_filters)" in page
    clear = page.split("def _clear_toolbar_filters", 1)[1].split(
        "def _on_filter_changed", 1
    )[0]
    assert "blockSignals(True)" in clear
    assert "self._load_server_page()" in clear
    assert clear.count("self._load_server_page()") == 1

    assert 'self.filter_btn.setText("More filters • Active")' in page
    assert 'self.filter_btn.setText("More filters")' in page


def test_student_refresh_preserves_current_list_context():
    page = _source("student_workspace/student_list_page.py")
    refresh = page.split("def refresh", 1)[1].split("def _load_server_page", 1)[0]

    assert "self._current_page = 1" not in refresh
    assert "self._advanced_filter_criteria" in refresh
    assert "self._filter_service.filter_students(" in refresh
