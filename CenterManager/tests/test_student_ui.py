# -*- coding: utf-8 -*-
"""
Integration UI tests for student list and add student flow.
"""
import pytest
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest

from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.services.student_service import StudentService
from centermanager.ui.students.student_list_page import StudentListPage
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.students.student_profile_dialog import StudentProfileDialog

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

@pytest.fixture
def service(test_db_path):
    from sqlalchemy.orm import sessionmaker
    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return StudentService(session_factory)

@pytest.fixture
def list_page(service, qapp):
    page = StudentListPage(service)
    page.show()
    QTest.qWaitForWindowExposed(page)
    return page

def test_student_list_refresh_empty(list_page):
    assert list_page.table.rowCount() == 0

def test_student_list_refresh_with_students(service, list_page):
    service.create_student(full_name="Test A")
    service.create_student(full_name="Test B")
    list_page.refresh()
    assert list_page.table.rowCount() == 2
    item = list_page.table.item(0, 0)
    assert item.text() == "HS001"

def test_search_filter(service, list_page):
    service.create_student(full_name="Nguyen Van An")
    service.create_student(full_name="Tran Minh Binh")
    list_page.refresh()

    list_page.search_input.setText("HS001")
    QTest.qWait(100)
    assert list_page.table.rowCount() == 1
    item = list_page.table.item(0, 1)
    assert "An" in item.text()

    list_page.search_input.setText("binh")
    QTest.qWait(100)
    assert list_page.table.rowCount() == 1
    item = list_page.table.item(0, 1)
    assert "Binh" in item.text()

    list_page.search_input.setText("nonexistent")
    QTest.qWait(100)
    assert list_page.table.rowCount() == 0

def test_add_student_dialog_flow(service, qapp):
    dialog = StudentFormDialog(service)
    dialog.full_name_edit.setText("Test Student")
    dialog.preferred_name_edit.setText("Tester")
    dialog._clear_dob()
    dialog.gender_combo.setCurrentText("Male")
    dialog.level_edit.setText("Intermediate")
    dialog.notes_edit.setPlainText("Some notes")

    dialog.save_btn.click()
    assert dialog.result() == StudentFormDialog.DialogCode.Accepted

    students = service.list_students()
    assert len(students) == 1
    s = students[0]
    assert s.full_name == "Test Student"
    assert s.preferred_name == "Tester"
    assert s.date_of_birth is None
    assert s.gender == "Male"
    assert s.current_level == "Intermediate"
    assert s.notes == "Some notes"

def test_profile_dialog_opens(service, qapp):
    student = service.create_student(full_name="Profile Test", preferred_name="P")
    dialog = StudentProfileDialog(service, student.id)
    assert dialog.code_label.text() == "HS001"
    assert dialog.name_label.text() == "Profile Test"
    assert dialog.preferred_label.text() == "P"

def test_dob_persistence(service, qapp):
    dialog = StudentFormDialog(service)
    dialog.dob_edit.setDate(QDate(2015, 6, 15))
    dialog.full_name_edit.setText("DOB Test")
    dialog.save_btn.click()
    assert dialog.result() == StudentFormDialog.DialogCode.Accepted

    students = service.list_students()
    assert len(students) == 1
    s = students[0]
    assert s.date_of_birth == date(2015, 6, 15)

def test_dob_clear(service, qapp):
    dialog = StudentFormDialog(service)
    dialog.dob_edit.setDate(QDate(2015, 6, 15))
    dialog._clear_dob()
    dialog.full_name_edit.setText("Clear DOB Test")
    dialog.save_btn.click()
    assert dialog.result() == StudentFormDialog.DialogCode.Accepted

    students = service.list_students()
    assert len(students) == 1
    s = students[0]
    assert s.date_of_birth is None

def test_dob_clear_then_set(service, qapp):
    dialog = StudentFormDialog(service)
    dialog._clear_dob()
    dialog.dob_edit.setDate(QDate(2010, 5, 20))
    dialog.full_name_edit.setText("Clear then set")
    dialog.save_btn.click()
    assert dialog.result() == StudentFormDialog.DialogCode.Accepted

    students = service.list_students()
    assert len(students) == 1
    s = students[0]
    assert s.date_of_birth == date(2010, 5, 20)

def test_profile_error_for_missing_student(service, qapp, monkeypatch):
    def mock_warning(*args, **kwargs):
        pass
    monkeypatch.setattr(QMessageBox, 'warning', mock_warning)
    dialog = StudentProfileDialog(service, 9999)
    assert dialog.code_label.text() == "Student not found"

def test_double_click_opens_profile(service, qapp, monkeypatch):
    student = service.create_student(full_name="Click Test")
    page = StudentListPage(service)
    page.refresh()
    assert page.table.rowCount() == 1

    captured_id = None
    class MockDialog:
        def __init__(self, service, student_id, parent):
            nonlocal captured_id
            captured_id = student_id
            self._service = service
            self._student_id = student_id
        def exec(self):
            return 0

    monkeypatch.setattr('centermanager.ui.students.student_list_page.StudentProfileDialog', MockDialog)

    index = page.table.model().index(0, 0)
    page._on_row_double_clicked(index)
    assert captured_id == student.id

def test_add_refresh_flow(service, qapp, monkeypatch):
    """Test that _on_add_clicked opens dialog, saves, and refreshes."""
    page = StudentListPage(service)
    assert page.table.rowCount() == 0

    class MockFormDialog:
        DialogCode = StudentFormDialog.DialogCode
        def __init__(self, service, parent):
            self._service = service
            self._parent = parent
        def exec(self):
            self._service.create_student(full_name="Refresh Test")
            return MockFormDialog.DialogCode.Accepted

    monkeypatch.setattr('centermanager.ui.students.student_list_page.StudentFormDialog', MockFormDialog)

    page._on_add_clicked()
    assert page.table.rowCount() == 1
    item = page.table.item(0, 0)
    assert item.text() == "HS001"