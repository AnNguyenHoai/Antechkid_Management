# -*- coding: utf-8 -*-
"""Regression contracts for scalable tuition Enrollment search in Finance."""
from decimal import Decimal
from pathlib import Path

from centermanager.services.income_service import TuitionEnrollmentChoice


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def test_repository_search_modes_preserve_archived_old_debt_without_polluting_active():
    source = (
        SRC / "repositories" / "enrollment_repository.py"
    ).read_text(encoding="utf-8")

    method = source.split("def search_tuition_payment_candidates(", 1)[1].split(
        "def list_for_outstanding", 1
    )[0]

    assert "Student.deleted_at.is_(None)" in method
    assert "Enrollment.reconciled_into_enrollment_id.is_(None)" in method
    assert 'normalized_mode == "ACTIVE"' in method
    assert 'Enrollment.status == "ACTIVE"' in method
    assert 'Student.status != "ARCHIVED"' in method
    assert "Class.deleted_at.is_(None)" in method
    assert 'normalized_mode == "OLD_DEBT"' in method
    assert 'Enrollment.status.in_(("WITHDRAWN", "COMPLETED"))' in method

    old_debt_section = method.split('normalized_mode == "OLD_DEBT"', 1)[1].split(
        "term =", 1
    )[0]
    assert 'Student.status != "ARCHIVED"' not in old_debt_section
    assert "Class.deleted_at.is_(None)" not in old_debt_section
    assert ".limit(max(1, min(int(limit or 20), 100)))" in method


def test_repository_search_supports_student_parent_class_and_course_terms():
    source = (
        SRC / "repositories" / "enrollment_repository.py"
    ).read_text(encoding="utf-8")
    method = source.split("def search_tuition_payment_candidates(", 1)[1].split(
        "def list_for_outstanding", 1
    )[0]

    for field in (
        "Student.student_code.ilike",
        "Student.full_name.ilike",
        "Student.preferred_name.ilike",
        "Parent.name.ilike",
        "Parent.phone.ilike",
        "Class.name.ilike",
        "Class.course.ilike",
        "Enrollment.class_name.ilike",
        "Enrollment.course_name.ilike",
    ):
        assert field in method


def test_income_service_projects_signed_outstanding_for_picker():
    choice = TuitionEnrollmentChoice(
        enrollment_id=11,
        student_id=2,
        student_name="Nguyen Van A",
        student_code="HS002",
        class_id=3,
        class_name="Python A",
        course_name="Python",
        enrollment_status="ACTIVE",
        outstanding=Decimal("-250000"),
        balance_state="PREPAID",
        tuition_configured=True,
    )

    assert choice.debt_amount == Decimal("0")
    assert choice.prepaid_amount == Decimal("250000")

    source = (SRC / "services" / "income_service.py").read_text(encoding="utf-8")
    assert "def search_tuition_enrollment_choices(" in source
    assert "search_tuition_payment_candidates(" in source
    assert "sum_active_tuition_for_enrollment(" in source
    assert "TuitionAccrualService.calculate_from_records(" in source


def test_picker_is_search_first_debounced_and_uses_clear_status_modes():
    source = (
        SRC / "ui" / "finance_workspace" / "tuition_enrollment_picker.py"
    ).read_text(encoding="utf-8")

    assert "QTimer" in source
    assert "setInterval(250)" in source
    assert "Tìm theo tên, mã HS, SĐT phụ huynh" in source
    assert 'addItem("Đang học", "ACTIVE")' in source
    assert 'addItem("Công nợ cũ", "OLD_DEBT")' in source
    assert 'addItem("Tất cả", "ALL")' in source
    assert 'mode=str(self.mode_combo.currentData() or "ACTIVE")' in source
    assert "limit=20" in source
    assert "Còn phải đóng" in source
    assert "Trả trước" in source
    assert "Enrollment #" in source


def test_tuition_create_uses_selected_enrollment_identity_not_three_dropdowns():
    source = (
        SRC / "ui" / "finance_workspace" / "income_form_dialog.py"
    ).read_text(encoding="utf-8")

    payload = source.split("def _create_identity_payload", 1)[1].split(
        "def _save", 1
    )[0]

    assert "choice = self.tuition_picker.selected_choice()" in payload
    assert "student_id = choice.student_id" in payload
    assert "class_id = choice.class_id" in payload
    assert "enrollment_id = choice.enrollment_id" in payload
    assert "Vui lòng tìm và chọn đúng Enrollment học phí." in payload


def test_create_filters_archived_but_edit_keeps_legacy_identity_visibility():
    source = (
        SRC / "ui" / "finance_workspace" / "income_form_dialog.py"
    ).read_text(encoding="utf-8")

    load_students = source.split("def _load_students", 1)[1].split(
        "def _load_classes", 1
    )[0]
    assert "self._student_service.list_active_non_archived_students()" in load_students
    assert "if self._is_edit" in load_students
    assert "self._student_service.list_students()" in load_students

    reload = source.split("def _reload_enrollments", 1)[1].split(
        "def _lock_identity_fields", 1
    )[0]
    assert "if not self._is_edit:" in reload
    assert "Create Tuition uses the search-first Enrollment picker" in reload


def test_student_service_exposes_non_archived_operational_list():
    source = (SRC / "services" / "student_service.py").read_text(encoding="utf-8")
    assert "def list_active_non_archived_students(" in source
    assert "return repo.list_active_non_archived()" in source

def test_old_debt_mode_filters_to_positive_historical_debt_and_keeps_archive_metadata():
    source = (SRC / "services" / "income_service.py").read_text(encoding="utf-8")
    method = source.split("def search_tuition_enrollment_choices(", 1)[1].split(
        "@require_permission", 1
    )[0]

    assert 'normalized_mode == "OLD_DEBT"' in method
    assert 'choice.enrollment_status in {"WITHDRAWN", "COMPLETED"}' in method
    assert "choice.tuition_configured" in method
    assert "choice.debt_amount > 0" in method
    assert "repository_limit = min(max(int(limit) * 5, 50), 100)" in method

    projection = source.split("def _tuition_choice_from_enrollment(", 1)[1].split(
        "def search_tuition_enrollment_choices(", 1
    )[0]
    assert 'student_status=getattr(student, "status", "ACTIVE") or "ACTIVE"' in projection
    assert 'class_archived=getattr(class_obj, "deleted_at", None) is not None' in projection


def test_picker_marks_archived_student_and_class_in_old_debt_results():
    source = (
        SRC / "ui" / "finance_workspace" / "tuition_enrollment_picker.py"
    ).read_text(encoding="utf-8")

    assert 'flags.append("HS ARCHIVED")' in source
    assert 'flags.append("LỚP ARCHIVED")' in source
    assert "Công nợ cũ: WITHDRAWN/COMPLETED" in source

