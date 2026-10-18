# -*- coding: utf-8 -*-
"""Regression contracts for icon, export authorization, and default Student filter."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_application_bootstrap_applies_runtime_icon():
    source = (ROOT / "src" / "centermanager" / "app.py").read_text(encoding="utf-8")
    assert "build_application_icon" in source
    assert "qapp.setWindowIcon(build_application_icon())" in source


def test_windows_release_embeds_explicit_icon():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert "generate_windows_icon()" in source
    assert '"--icon", str(windows_icon)' in source


def test_student_export_service_enforces_capability_at_service_boundary():
    source = (
        ROOT / "src" / "centermanager" / "services" / "student_export_service.py"
    ).read_text(encoding="utf-8")
    assert source.count('@require_permission("student.export")') >= 3


def test_reception_role_does_not_implicitly_gain_student_export():
    source = (ROOT / "src" / "centermanager" / "database" / "seed.py").read_text(
        encoding="utf-8"
    )
    reception_block = source.split("# Reception", 1)[1].split("# Finance", 1)[0]
    assert "PermissionDefinitions.STUDENT_EXPORT" not in reception_block


def test_student_list_defaults_status_filter_to_active_and_gates_export_ui():
    source = (
        ROOT / "src" / "centermanager" / "ui" / "student_workspace" / "student_list_page.py"
    ).read_text(encoding="utf-8")
    assert 'self.search_bar.set_filter_value("status", "Active")' in source
    assert "Capability.STUDENT_EXPORT" in source
    assert "self.export_btn.setEnabled(can_export)" in source
    assert "self.bulk_export_btn.setEnabled(can_export)" in source
