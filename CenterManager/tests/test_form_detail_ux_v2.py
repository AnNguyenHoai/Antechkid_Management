# -*- coding: utf-8 -*-
"""Regression coverage for UI-PROD-06 Form & Detail UX."""
from pathlib import Path
import re

from centermanager.ui.design_system import (
    Button,
    DetailRow,
    DetailSection,
    EditStateBanner,
    FormField,
    FormSection,
    Input,
    Select,
)
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.student_workspace.profile_widget import ProfileWidget
from centermanager.ui.student_workspace.quick_actions_widget import QuickActionsWidget


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager" / "ui"
RAW_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]"
)


def test_form_field_propagates_inline_validation(qapplication_session):
    control = Input("Student name")
    field = FormField("Full Name", control, required=True, helper_text="Required")

    field.set_error("Name is required")
    assert field.has_error is True
    assert field.error_message == "Name is required"
    assert control.has_error is True
    assert field.message_label.text() == "Name is required"

    field.clear_error()
    assert field.has_error is False
    assert control.has_error is False
    assert field.message_label.text() == "Required"


def test_form_section_composes_existing_controls(qapplication_session):
    section = FormSection("Student information", "Core profile")
    name_field = FormField("Name", Input())
    gender_field = FormField("Gender", Select(["", "Male", "Female"]))

    assert section.add_field(name_field) is name_field
    assert section.add_field(gender_field) is gender_field
    assert section.fields_layout.count() == 2


def test_detail_patterns_are_mutable_without_domain_logic(qapplication_session):
    section = DetailSection("Student profile")
    row = section.add_row("Current Level", "Python Beginner")

    assert isinstance(row, DetailRow)
    assert row.value == "Python Beginner"

    row.set_value(None)
    assert row.value == "—"


def test_edit_state_banner_has_explicit_operational_states(qapplication_session):
    banner = EditStateBanner("readonly")
    assert banner.state == "readonly"

    banner.set_state("editing")
    assert banner.state == "editing"
    assert "Editing" in banner.title_label.text()

    banner.set_state("locked", "Another user is editing this record.")
    assert banner.state == "locked"
    assert banner.message_label.text() == "Another user is editing this record."


def test_student_form_preserves_public_contract(qapplication_session):
    class ServiceStub:
        pass

    dialog = StudentFormDialog(ServiceStub())
    assert isinstance(dialog.full_name_edit, Input)
    assert isinstance(dialog.gender_combo, Select)
    assert isinstance(dialog.save_btn, Button)
    assert hasattr(dialog, "preferred_name_edit")
    assert hasattr(dialog, "dob_edit")
    assert hasattr(dialog, "level_edit")
    assert hasattr(dialog, "notes_edit")
    assert hasattr(dialog, "cancel_btn")


def test_student_profile_uses_detail_pattern(qapplication_session):
    widget = ProfileWidget()
    assert isinstance(widget.profile_section, DetailSection)
    assert hasattr(widget, "details_grid")
    assert hasattr(widget, "status_badge")
    assert hasattr(widget, "image_label")


def test_student_detail_actions_preserve_write_contract(qapplication_session):
    actions = QuickActionsWidget()

    actions.set_write_enabled(False)
    assert actions.edit_state_banner.state == "readonly"
    assert actions.edit_btn.isEnabled() is False
    assert actions.export_pdf_btn.isEnabled() is True

    actions.set_write_enabled(True)
    assert actions.edit_state_banner.state == "editing"
    assert actions.edit_btn.isEnabled() is True


def test_migrated_form_detail_sources_have_no_raw_palette_or_visual_emoji_literals():
    migrated = [
        SRC / "design_system" / "form_detail.py",
        SRC / "students" / "student_form_dialog.py",
        SRC / "student_workspace" / "profile_widget.py",
        SRC / "student_workspace" / "quick_actions_widget.py",
    ]

    for path in migrated:
        source = path.read_text(encoding="utf-8")
        assert not RAW_HEX.search(source), f"raw color found in {path.name}"
        # UI-PROD-07's canonical save acknowledgement may contain a checkmark;
        # the visual-UI regression guard still rejects other raw emoji literals.
        visual_source = source.replace("Student saved ✓", "Student saved")
        assert not EMOJI.search(visual_source), f"emoji literal found in {path.name}"
        assert "from centermanager.ui import styles" not in source