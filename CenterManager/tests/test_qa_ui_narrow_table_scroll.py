"""UI-AUDIT: long financial and attendance columns stay readable in narrow views.

All controls are created in memory with synthetic/empty data; no DB or Git
access is performed.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

from centermanager.ui.student_workspace.student_financial_widget import StudentFinancialWidget
from centermanager.ui.class_workspace.monthly_attendance_exceptions_page import MonthlyAttendanceExceptionsPage
from centermanager.ui.finance_workspace.outstanding_list_page import OutstandingListPage


def _assert_horizontal_scroll(table, qapp):
    table.resize(465, 260)
    table.show()
    qapp.processEvents()
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert table.horizontalHeader().stretchLastSection() is False
    assert table.horizontalHeader().sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert table.horizontalScrollBar().maximum() > 0
    table.hide()


def test_student_financial_tables_scroll_instead_of_compress(qapp):
    widget = StudentFinancialWidget(None, None, None, None, None)
    for table in (widget.detail_data_table.table, widget.payment_table.table):
        _assert_horizontal_scroll(table, qapp)


def test_monthly_attendance_nine_columns_scroll_in_narrow_view(qapp):
    page = MonthlyAttendanceExceptionsPage(None, None)
    _assert_horizontal_scroll(page.table.table, qapp)


def test_outstanding_seven_columns_scroll_in_narrow_view(qapp):
    page = OutstandingListPage(None, None, None)
    _assert_horizontal_scroll(page.data_table.table, qapp)
