from datetime import date, time
from types import SimpleNamespace

from PySide6.QtCore import QDate

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.ui.employee_workspace.employee_work_registration_widget import (
    EmployeeWorkRegistrationWidget,
    WorkRegistrationDialog,
)


class FakeService:
    def __init__(self, registration=None):
        self.registration = registration
        self.refresh_calls = 0

    def next_month(self):
        return 2026, 10

    def list_for_employee(self, employee_id, year, month):
        return self.registration

    def get_period(self, year, month):
        return SimpleNamespace(submission_deadline=date(2026, 10, 25))


def test_empty_registration_is_editable_in_draft(qtbot):
    service = FakeService(None)
    employee = SimpleNamespace(id=1)
    widget = EmployeeWorkRegistrationWidget(service, employee, editable=True)
    qtbot.addWidget(widget)

    assert widget.status.text() == EmployeeWorkRegistration.STATUS_DRAFT
    assert widget.add.isEnabled()
    assert not widget.edit.isEnabled()
    assert not widget.delete.isEnabled()
    assert not widget.submit.isEnabled()


def test_refresh_clears_stale_selection_after_reload(qtbot):
    block = SimpleNamespace(
        id=7,
        work_date=date(2026, 10, 3),
        start_time=time(9, 0),
        end_time=time(12, 0),
        work_type="WORK",
        notes=None,
    )
    registration = SimpleNamespace(
        status=EmployeeWorkRegistration.STATUS_DRAFT,
        blocks=[block],
        submitted_at=None,
        accepted_at=None,
    )
    service = FakeService(registration)
    widget = EmployeeWorkRegistrationWidget(service, SimpleNamespace(id=1), editable=True)
    qtbot.addWidget(widget)
    widget.table.selectRow(0)
    assert widget._selected() is block

    widget.refresh()
    assert widget.table.currentRow() == -1
    assert widget._selected() is None
    assert not widget.edit.isEnabled()
    assert not widget.delete.isEnabled()


def test_dialog_enforces_date_bounds(qtbot):
    dialog = WorkRegistrationDialog(
        default_date=date(2026, 10, 1),
        min_date=date(2026, 10, 1),
        max_date=date(2026, 10, 31),
    )
    qtbot.addWidget(dialog)
    assert dialog.day.minimumDate() == QDate(2026, 10, 1)
    assert dialog.day.maximumDate() == QDate(2026, 10, 31)
