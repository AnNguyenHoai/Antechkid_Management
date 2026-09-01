from types import SimpleNamespace
from unittest.mock import Mock, patch

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.ui.employee_workspace.employee_work_registration_review_page import (
    EmployeeWorkRegistrationReviewPage,
)


def _registration(status, employee_id=1):
    employee = SimpleNamespace(full_name="Employee", employee_code="E001")
    return SimpleNamespace(
        employee_id=employee_id,
        employee=employee,
        blocks=[],
        status=status,
        submitted_at=None,
        accepted_at=None,
    )


def test_filter_by_status_and_selection(qtbot):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    registration_service.list_all.return_value = [
        _registration(EmployeeWorkRegistration.STATUS_DRAFT, 1),
        _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 2),
        _registration(EmployeeWorkRegistration.STATUS_ACCEPTED, 3),
    ]

    page = EmployeeWorkRegistrationReviewPage(employee_service, registration_service)
    qtbot.addWidget(page)

    assert page.table.rowCount() == 3
    page.status_filter.setCurrentText("SUBMITTED")
    assert page.table.rowCount() == 1
    assert page._selected().status == EmployeeWorkRegistration.STATUS_SUBMITTED


def test_filter_rebuild_does_not_reenter_action_update(qtbot):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    registration_service.list_all.return_value = [
        _registration(EmployeeWorkRegistration.STATUS_DRAFT, 1),
        _registration(EmployeeWorkRegistration.STATUS_SUBMITTED, 2),
    ]

    page = EmployeeWorkRegistrationReviewPage(employee_service, registration_service)
    qtbot.addWidget(page)

    with patch.object(page, "_update_actions", wraps=page._update_actions) as update_actions:
        update_actions.reset_mock()
        page.status_filter.setCurrentText("SUBMITTED")
        qtbot.wait(1)

        assert page.table.rowCount() == 1
        assert page._selected() is None
        assert update_actions.call_count == 1


def test_accept_selected_calls_service_and_refreshes(qtbot):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    submitted = _registration(EmployeeWorkRegistration.STATUS_SUBMITTED)
    registration_service.list_all.side_effect = [[submitted], [_registration(EmployeeWorkRegistration.STATUS_ACCEPTED)]]

    page = EmployeeWorkRegistrationReviewPage(employee_service, registration_service)
    qtbot.addWidget(page)
    page.table.selectRow(0)

    with patch("centermanager.ui.employee_workspace.employee_work_registration_review_page.QMessageBox.question", return_value=2):
        page.accept_selected()

    registration_service.accept.assert_called_once_with(1, 2026, 10)


def test_reopen_selected_calls_service(qtbot):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    accepted = _registration(EmployeeWorkRegistration.STATUS_ACCEPTED)
    registration_service.list_all.return_value = [accepted]

    page = EmployeeWorkRegistrationReviewPage(employee_service, registration_service)
    qtbot.addWidget(page)
    page.table.selectRow(0)

    with patch("centermanager.ui.employee_workspace.employee_work_registration_review_page.QMessageBox.question", return_value=2):
        page.reopen_selected()

    registration_service.reopen.assert_called_once_with(1, 2026, 10)


def test_actions_disabled_without_write(qtbot):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    registration_service.list_all.return_value = [_registration(EmployeeWorkRegistration.STATUS_SUBMITTED)]

    page = EmployeeWorkRegistrationReviewPage(employee_service, registration_service)
    qtbot.addWidget(page)
    page.table.selectRow(0)
    page.set_write_enabled(False)

    assert not page.accept_btn.isEnabled()
    assert not page.reopen_btn.isEnabled()
