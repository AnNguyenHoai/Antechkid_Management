from types import SimpleNamespace
from unittest.mock import Mock, patch

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
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


def _page(qtbot, period_status):
    employee_service = Mock()
    registration_service = Mock()
    registration_service.next_month.return_value = (2026, 10)
    registration_service.get_period.return_value = SimpleNamespace(status=period_status)
    registration_service.list_all.return_value = [
        _registration(EmployeeWorkRegistration.STATUS_ACCEPTED)
    ]
    page = EmployeeWorkRegistrationReviewPage(employee_service, registration_service)
    qtbot.addWidget(page)
    page.set_write_enabled(True)
    page.table.selectRow(0)
    return page, registration_service


def test_closed_period_is_reflected_in_review_page(qtbot):
    page, _ = _page(qtbot, EmployeeWorkRegistrationPeriod.STATUS_CLOSED)

    assert page._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
    assert "Period: Closed" in page.month.text()
    assert not page.accept_btn.isEnabled()
    assert not page.reopen_btn.isEnabled()
    assert not page.close_btn.isEnabled()


def test_open_period_keeps_close_action_available_when_all_accepted(qtbot):
    page, _ = _page(qtbot, EmployeeWorkRegistrationPeriod.STATUS_OPEN)

    assert "Period: Open" in page.month.text()
    assert page.close_btn.isEnabled()
    assert page.reopen_btn.isEnabled()


def test_close_refreshes_period_status(qtbot):
    page, registration_service = _page(qtbot, EmployeeWorkRegistrationPeriod.STATUS_OPEN)

    period_state = {"status": EmployeeWorkRegistrationPeriod.STATUS_OPEN}
    registration_service.get_period.side_effect = lambda *args, **kwargs: SimpleNamespace(
        status=period_state["status"]
    )
    registration_service.close_month.side_effect = lambda year, month: period_state.update(
        status=EmployeeWorkRegistrationPeriod.STATUS_CLOSED
    )

    with patch(
        "centermanager.ui.employee_workspace.employee_work_registration_review_page.QMessageBox.question",
        return_value=16384,
    ):
        page.close_month()

    registration_service.close_month.assert_called_once_with(2026, 10)
    registration_service.get_period.assert_called()
    assert page._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
    assert "Period: Closed" in page.month.text()
    assert not page.close_btn.isEnabled()
    assert not page.reopen_btn.isEnabled()
