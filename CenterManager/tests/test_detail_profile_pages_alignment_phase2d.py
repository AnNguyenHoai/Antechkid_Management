# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2D detail/profile page alignment."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_shared_entity_header_uses_vector_identity_status_and_action_zone():
    source = _source("shared/entity_header.py")

    assert "class EntityHeader(QFrame):" in source
    assert "self.icon = AppIcon(" in source
    assert 'self.title_label.setObjectName("EntityHeaderTitle")' in source
    assert 'self.status_label.setObjectName("EntityHeaderStatus")' in source
    assert "def add_action" in source
    assert "def set_identity" in source
    assert "def set_status" in source


def test_student_detail_remains_v2_reference_surface():
    source = _source("student_workspace/student_detail_page.py")
    profile = _source("student_workspace/profile_widget.py")

    assert "toolbar = Toolbar(self)" in source
    assert "self.tab_widget = Tabs(" in source
    assert "DetailSection(" in source
    assert "self.profile_section = DetailSection(" in profile
    assert "DetailRow(" in profile


def test_class_detail_uses_shared_entity_header_and_canonical_toolbar():
    source = _source("class_workspace/class_detail_page.py")

    assert "toolbar = Toolbar(self)" in source
    assert 'self.entity_header = EntityHeader(' in source
    assert 'icon="class"' in source
    assert 'self.edit_btn = PrimaryButton("Edit")' in source
    assert 'self.entity_header.add_action(self.edit_btn)' in source
    assert '"Assigned Teachers"' in source
    assert '"Enrolled Students"' in source
    assert '"Timeline"' in source
    assert "📚" not in source
    assert "✏️" not in source


def test_teacher_detail_uses_shared_entity_header_without_emoji_actions():
    source = _source("teacher_workspace/teacher_detail_page.py")

    assert "toolbar = Toolbar(self)" in source
    assert 'self.entity_header = EntityHeader(' in source
    assert 'icon="teacher"' in source
    assert 'self.edit_btn = PrimaryButton("Edit")' in source
    assert 'self.restore_btn = PrimaryButton("Restore")' in source
    assert "self.entity_header.set_identity(" in source
    assert "📚" not in source
    assert "↩" not in source


def test_employee_profile_uses_shared_entity_header_tabs_and_buttons():
    source = _source("employee_workspace/employee_list_page.py")
    profile = source.split("class EmployeeProfileDialog", 1)[1].split(
        "class EmployeeListPage", 1
    )[0]

    assert 'self.entity_header = EntityHeader(' in profile
    assert 'icon="employee"' in profile
    assert "self.tabs = Tabs(self)" in profile
    assert 'self.entity_header.set_identity(' in profile
    assert 'variant=ButtonVariant.PRIMARY' in profile
    assert 'variant=ButtonVariant.SECONDARY' in profile
    assert "📄" not in profile


def test_finance_detail_dialogs_use_shared_read_only_detail_presentation():
    income = _source("finance_workspace/income_detail_dialog.py")
    expense = _source("finance_workspace/expense_detail_dialog.py")
    tuition = _source("finance_workspace/tuition_detail_dialog.py")

    assert 'detail_section = DetailSection(' in income
    assert 'detail_section = DetailSection(' in expense
    assert 'close_btn = Button(' in income
    assert 'close_btn = Button(' in expense
    assert "tabs = Tabs(self)" in tuition
    assert 'layout.setContentsMargins(SPACING["lg"]' in tuition


def test_phase_2d_does_not_change_detail_business_service_calls():
    class_detail = _source("class_workspace/class_detail_page.py")
    teacher_detail = _source("teacher_workspace/teacher_detail_page.py")
    employee = _source("employee_workspace/employee_list_page.py")
    income = _source("finance_workspace/income_detail_dialog.py")
    expense = _source("finance_workspace/expense_detail_dialog.py")

    assert "get_class_with_details(class_id)" in class_detail
    assert "get_teacher_with_details(teacher_id)" in teacher_detail
    assert "get_archived_teacher(teacher_id)" in teacher_detail
    assert "self.s.update_employee(self.employee.id, **self._payload())" in employee
    assert "self._service.get_income(self._income_id)" in income
    assert "self._service.get_expense(self._expense_id)" in expense
