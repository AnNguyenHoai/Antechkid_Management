from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import Qt

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.ui.employee_workspace.employee_work_registration_review_page import (
    EmployeeWorkRegistrationReviewPage,
)


def _registration(status, employee_id, registration_id):
    employee = SimpleNamespace(
        full_name=f"Employee {employee_id}",
        employee_code=f"E{employee_id:03d}",
    )
    return SimpleNamespace(
        id=registration_id,
        employee_id=employee_id,
        employee=employee,
        blocks=[],
        status=status,
        submitted_at=None,
        accepted_at=None,
    )


def _page(registrations):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    registration_service.list_all.return_value = registrations
    return EmployeeWorkRegistrationReviewPage(employee_service, registration_service)


def test_same_employee_different_registration_ids_have_distinct_selection_identity(qtbot):
    first = _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 1, 101)
    second = _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 1, 102)

    page = _page([first, second])
    qtbot.addWidget(page)
    page.table.selectRow(1)

    assert page._selected_registration_id == ("registration", 102)
    assert page._selected() is second
    assert page.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == ("registration", 101)
    assert page.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == ("registration", 102)


def test_selection_resolves_to_current_registration_object_after_data_refresh(qtbot):
    original = _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 1, 101)
    other = _registration(EmployeeWorkRegistration.STATUS_DRAFT, 2, 202)

    page = _page([original, other])
    qtbot.addWidget(page)
    page.table.selectRow(0)

    replacement = _registration(EmployeeWorkRegistration.STATUS_ACCEPTED, 1, 101)
    replacement_other = _registration(EmployeeWorkRegistration.STATUS_DRAFT, 2, 202)
    page._rows = [replacement, replacement_other]
    page._apply_filter()

    assert page._selected_registration_id == ("registration", 101)
    assert page._selected() is replacement
    assert page._selected() is not original
    assert page._selected().status == EmployeeWorkRegistration.STATUS_ACCEPTED


def test_selection_identity_follows_registration_when_row_order_changes(qtbot):
    first = _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 1, 101)
    second = _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 2, 202)
    third = _registration(EmployeeWorkRegistration.STATUS_ACCEPTED, 3, 303)

    page = _page([first, second, third])
    qtbot.addWidget(page)
    page.table.selectRow(1)

    page._rows = [third, second, first]
    page._apply_filter()

    assert page._selected_registration_id == ("registration", 202)
    assert page._selected() is second
    assert page.table.currentRow() == 1
    assert page.table.item(1, 0).data(Qt.ItemDataRole.UserRole) == ("registration", 202)
