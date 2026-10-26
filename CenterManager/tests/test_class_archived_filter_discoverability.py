# -*- coding: utf-8 -*-
"""Regression contracts for archived Class discoverability in Class Workspace."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "src" / "centermanager" / "ui" / "class_workspace" / "class_list_page.py"


def _source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_class_list_loads_archived_records_for_local_status_filtering():
    source = _source()

    assert 'self._class_service.list_classes(include_archived=True)' in source
    assert '"options": ["Active", "Inactive", "Archived"]' in source
    assert 'if status_label == "Archived":' in source
    assert 'if class_obj.deleted_at is not None' in source


def test_archived_class_rows_render_archived_status_and_offer_restore():
    source = _source()

    assert '"status": "ARCHIVED" if c.deleted_at is not None else (c.status or "ACTIVE")' in source
    assert 'restore_action = QAction("Restore Class", self)' in source
    assert 'self._class_service.restore_class(class_id)' in source
    assert '"You must be in WRITE mode to restore a class."' in source
    assert 'if class_obj.deleted_at is None:' in source
    assert '"Archived class is read-only. Restore it before opening the class workspace."' in source


def test_active_filter_remains_default_after_archived_support():
    source = _source()

    assert 'self.search_bar.set_filter_value("status", "Active")' in source
    assert 'status_map = {"Active": "ACTIVE", "Inactive": "INACTIVE"}' in source
    assert 'class_obj.deleted_at is None' in source
