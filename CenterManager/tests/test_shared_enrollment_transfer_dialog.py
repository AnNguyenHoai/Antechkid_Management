# -*- coding: utf-8 -*-
"""Regression contracts for the shared Enrollment transfer UI."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def test_shared_transfer_dialog_owns_target_credit_preview_and_submit():
    source = (SRC / "ui" / "enrollment_transfer_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "class EnrollmentTransferDialog(QDialog)" in source
    assert "self._transfer_service.preview(" in source
    assert "available_prepaid_credit" in source
    assert "self.credit_input.setMaximum(available)" in source
    assert "self.credit_input.setValue(available)" in source
    assert "A transfer reason is required." in source
    assert "self._transfer_service.transfer(" in source
    assert "transferred_credit=self.credit_input.value()" in source


def test_student_enrollment_transfer_no_longer_depends_on_enroll_selector():
    source = (
        SRC / "ui" / "student_workspace" / "enrollment_widget.py"
    ).read_text(encoding="utf-8")

    transfer_body = source.split("def _transfer(self, enrollment)", 1)[1].split(
        "def _refund", 1
    )[0]

    assert "EnrollmentTransferDialog(" in transfer_body
    assert "self.class_combo.currentData()" not in transfer_body
    assert "same selection is used as the transfer target" not in source
    assert 'setAccessibleName("Class to enroll into")' in source


def test_class_detail_exposes_transfer_beside_withdraw():
    source = (
        SRC / "ui" / "class_workspace" / "class_detail_page.py"
    ).read_text(encoding="utf-8")

    student_block = source.split("def _update_students", 1)[1].split(
        "def _clear_layout", 1
    )[0]
    transfer_handler = source.split("def _on_transfer_student", 1)[1].split(
        "def _on_withdraw_student", 1
    )[0]

    assert 'QPushButton("Transfer")' in student_block
    assert 'QPushButton("Withdraw")' in student_block
    assert "_on_transfer_student" in student_block
    assert "get_active_enrollment(" in transfer_handler
    assert "EnrollmentTransferDialog(" in transfer_handler
    assert "Student transferred to target class." in transfer_handler


def test_class_service_exposes_transfer_ui_reads_without_ui_repository_access():
    source = (SRC / "services" / "class_service.py").read_text(encoding="utf-8")
    transfer = (
        SRC / "services" / "enrollment_transfer_service.py"
    ).read_text(encoding="utf-8")
    dialog = (SRC / "ui" / "enrollment_transfer_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "def get_active_enrollment(" in source
    assert "def get_student_enrollments(" in source
    assert "def from_class_service(cls, class_service)" in transfer
    assert "_repository_provider" not in dialog
    assert "_session_factory" not in dialog
