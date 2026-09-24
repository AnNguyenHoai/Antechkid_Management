# -*- coding: utf-8 -*-
"""Income Workspace list: real pagination, server sorting, lifecycle and export."""
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from centermanager.core.capabilities import Capability
from centermanager.core.clock import get_clock
from centermanager.models.income import Income
from centermanager.platform.collaboration import CollaborationManager
from centermanager.services.class_service import ClassService
from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.ui.design_system import (
    PrimaryButton,
    SearchBar,
    SecondaryButton,
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.finance_workspace.action_state import can_mutate
from centermanager.ui.finance_workspace.income_detail_dialog import IncomeDetailDialog
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog
from centermanager.ui.shared import DataTable, LoadingWidget

logger = logging.getLogger(__name__)


class IncomeListPage(QWidget):
    income_selected = Signal(int)

    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        collaboration_manager: CollaborationManager,
        notification_service=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service

        self._incomes = []
        self._write_enabled = False
        self._period_closed = False
        self._target_date = get_clock().today()
        self._period_start: Optional[date] = None
        self._period_end: Optional[date] = None
        self._period_configured = None

        self._current_page = 1
        self._page_size = 20
        self._total_rows = 0
        self._sort_by = "payment_date"
        self._sort_ascending = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background: {COLORS['surface']}; "
            f"padding: {SPACING['sm']}px {SPACING['md']}px; "
            f"border-bottom: 1px solid {COLORS['border_light']};"
        )
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        self.search_bar = SearchBar(
            "Tìm theo học sinh, mã HS, lớp, loại, ghi chú, người thu..."
        )
        self.search_bar.text_changed.connect(self._filters_changed)
        top_row.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Làm mới")
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.export_btn = SecondaryButton("⬇ Xuất CSV")
        self.export_btn.clicked.connect(self._export_csv)
        top_row.addWidget(self.export_btn)

        self.add_btn = PrimaryButton("+ Thêm thu nhập")
        self.add_btn.clicked.connect(self._show_add_dialog)
        top_row.addWidget(self.add_btn)
        toolbar_layout.addLayout(top_row)

        filters = QHBoxLayout()

        self.type_combo = QComboBox()
        self.type_combo.addItem("Tất cả loại", "")
        for value in ["Tuition", "Book", "Robot Kit", "Material", "Other"]:
            self.type_combo.addItem(value, value)
        self.type_combo.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Loại:"))
        filters.addWidget(self.type_combo)

        self.method_combo = QComboBox()
        self.method_combo.addItem("Tất cả wallet", "")
        self.method_combo.addItem("Cash", "CASH")
        self.method_combo.addItem("Bank", "BANK")
        self.method_combo.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Wallet:"))
        filters.addWidget(self.method_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Đang hiệu lực", Income.STATUS_ACTIVE)
        self.status_combo.addItem("Đã void", Income.STATUS_VOIDED)
        self.status_combo.addItem("Tất cả trạng thái", "ALL")
        self.status_combo.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Trạng thái:"))
        filters.addWidget(self.status_combo)

        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_from_edit.setDate(QDate.currentDate().addDays(-30))
        self.date_from_edit.dateChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Từ:"))
        filters.addWidget(self.date_from_edit)

        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_to_edit.setDate(QDate.currentDate())
        self.date_to_edit.dateChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Đến:"))
        filters.addWidget(self.date_to_edit)

        filters.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc")
        clear_btn.clicked.connect(self._clear_filters)
        filters.addWidget(clear_btn)
        toolbar_layout.addLayout(filters)
        layout.addWidget(toolbar)

        columns = [
            {"key": "payment_date", "label": "Ngày", "sortable": True},
            {"key": "source", "label": "Nguồn thu", "sortable": False},
            {"key": "student_name", "label": "Học sinh", "sortable": False},
            {"key": "class_name", "label": "Lớp", "sortable": False},
            {"key": "income_type", "label": "Loại", "sortable": True},
            {"key": "amount", "label": "Số tiền", "sortable": True},
            {"key": "payment_method", "label": "Wallet", "sortable": True},
            {"key": "payment_period", "label": "Kỳ ghi chú", "sortable": True},
            {"key": "status", "label": "Trạng thái", "sortable": False},
            {"key": "received_by", "label": "Người thu", "sortable": True},
            {"key": "note", "label": "Ghi chú", "sortable": False},
        ]
        self.data_table = DataTable(columns, page_size=self._page_size)
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.page_requested.connect(self._on_page_requested)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
        layout.addWidget(self.data_table)

        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)
        self._apply_action_state()

    def _notify(self, message: str, level: str = "warning") -> None:
        if self._notification_service is not None and hasattr(
            self._notification_service, "notify"
        ):
            self._notification_service.notify(message, level)
        else:
            logger.warning("Finance notification fallback: %s", message)

    @staticmethod
    def _to_qdate(value: date) -> QDate:
        return QDate(value.year, value.month, value.day)

    def _reset_date_filters_to_period(self) -> None:
        if self._period_start is None or self._period_end is None:
            return
        for widget, value in (
            (self.date_from_edit, self._period_start),
            (self.date_to_edit, self._period_end),
        ):
            previous = widget.blockSignals(True)
            widget.setDate(self._to_qdate(value))
            widget.blockSignals(previous)

    def refresh(
        self,
        *_args,
        target_date=None,
        period_start=None,
        period_end=None,
        period_configured=None,
        period_closed=None,
        **_kwargs,
    ) -> None:
        if target_date is not None:
            self._target_date = target_date
        period_changed = (
            period_start is not None
            and period_end is not None
            and (
                period_start != self._period_start
                or period_end != self._period_end
            )
        )
        if period_configured is not None:
            self._period_configured = period_configured
        if period_closed is not None:
            self._period_closed = bool(period_closed)
        if period_start is not None and period_end is not None:
            self._period_start = period_start
            self._period_end = period_end
            if period_changed:
                self._reset_date_filters_to_period()
                self._current_page = 1
        elif period_configured is False:
            self._period_start = None
            self._period_end = None
            self._period_closed = False
            self._current_page = 1

        self._apply_action_state()
        self.loading.setVisible(True)
        try:
            self._load_page()
        except Exception as exc:
            logger.exception("Failed to refresh Income Workspace")
            QMessageBox.critical(self, "Lỗi", str(exc))
        finally:
            self.loading.setVisible(False)

    def _default_transaction_date(self) -> date:
        today = get_clock().today()
        if self._period_start is None or self._period_end is None:
            return self._target_date or today
        if self._period_start <= today <= self._period_end:
            return today
        if self._period_start <= self._target_date <= self._period_end:
            return self._target_date
        return self._period_start

    def _effective_date_bounds(self):
        user_from = self.date_from_edit.date().toPython()
        user_to = self.date_to_edit.date().toPython()
        if self._period_start is None or self._period_end is None:
            return user_from, user_to
        return (
            max(user_from, self._period_start),
            min(user_to, self._period_end),
        )

    def _filter_kwargs(self) -> dict:
        date_from, date_to = self._effective_date_bounds()
        return {
            "income_type": self.type_combo.currentData() or None,
            "payment_method": self.method_combo.currentData() or None,
            "date_from": date_from,
            "date_to": date_to,
            "search_text": self.search_bar.text().strip() or None,
            "status": self.status_combo.currentData() or Income.STATUS_ACTIVE,
        }

    def _filters_changed(self, *_args) -> None:
        self._current_page = 1
        self._load_page()

    def _load_page(self) -> None:
        if self._period_configured is False:
            self._incomes = []
            self._total_rows = 0
            self._populate_table()
            return

        kwargs = self._filter_kwargs()
        if kwargs["date_from"] > kwargs["date_to"]:
            self._incomes = []
            self._total_rows = 0
            self._populate_table()
            return

        items, total = self._income_service.list_incomes(
            **kwargs,
            finance_period_start=self._period_start,
            page=self._current_page,
            per_page=self._page_size,
            sort_by=self._sort_by,
            ascending=self._sort_ascending,
        )

        max_page = max(1, (total + self._page_size - 1) // self._page_size)
        if self._current_page > max_page:
            self._current_page = max_page
            items, total = self._income_service.list_incomes(
                **kwargs,
                finance_period_start=self._period_start,
                page=self._current_page,
                per_page=self._page_size,
                sort_by=self._sort_by,
                ascending=self._sort_ascending,
            )

        self._incomes = items
        self._total_rows = total
        self._populate_table()

    def _populate_table(self) -> None:
        data = []
        for income in self._incomes:
            linked = income.student_id is not None
            data.append(
                {
                    "payment_date": income.payment_date.strftime("%d/%m/%Y"),
                    "source": "STUDENT_PAYMENT" if linked else "OTHER_INCOME",
                    "student_name": income.student.full_name if linked and income.student else "-",
                    "class_name": income.class_.name if linked and income.class_ else "-",
                    "income_type": income.income_type,
                    "amount": f"{income.amount:,.0f}",
                    "payment_method": income.payment_method,
                    "payment_period": income.payment_period or "-",
                    "status": income.status,
                    "received_by": income.received_by or "-",
                    "note": income.note or "-",
                }
            )
        self.data_table.set_server_data(
            data,
            self._total_rows,
            page=self._current_page,
            page_size=self._page_size,
        )

    def _on_page_requested(self, page: int, page_size: int) -> None:
        self._current_page = page
        self._page_size = page_size
        self._load_page()

    def _on_sort(self, key: str, ascending: bool) -> None:
        getters = {
            "payment_date": lambda item: item.payment_date,
            "income_type": lambda item: item.income_type or "",
            "amount": lambda item: item.amount,
            "payment_method": lambda item: item.payment_method or "",
            "payment_period": lambda item: item.payment_period or "",
            "received_by": lambda item: item.received_by or "",
        }
        getter = getters.get(key)
        if getter is None:
            return
        self._sort_by = key
        self._sort_ascending = ascending
        self._current_page = 1
        self._load_page()
        self._incomes.sort(key=getter, reverse=not ascending)
        self._populate_table()

    def _on_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._incomes):
            self._show_detail_dialog(self._incomes[row].id)

    def _can(self, capability) -> bool:
        return can_mutate(
            write_enabled=self._write_enabled,
            capability=capability,
            domain_allowed=not self._period_closed,
        )

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._incomes):
            return

        income = self._incomes[row]
        menu = QMenu(self)
        menu.addAction("Xem", lambda: self._show_detail_dialog(income.id))

        if income.status == Income.STATUS_ACTIVE:
            edit_action = menu.addAction("Sửa", lambda: self._show_edit_dialog(income.id))
            edit_action.setEnabled(self._can(Capability.FINANCE_INCOME_UPDATE))
            void_action = menu.addAction("Void", lambda: self._void_income(income.id))
            void_action.setEnabled(self._can(Capability.FINANCE_INCOME_DELETE))
        elif income.status == Income.STATUS_VOIDED:
            delete_action = menu.addAction(
                "Xóa (soft delete)", lambda: self._delete_income(income.id)
            )
            delete_action.setEnabled(self._can(Capability.FINANCE_INCOME_DELETE))

        menu.exec(pos)

    def _ensure_action(self, capability, action: str) -> bool:
        if not self._can(capability):
            self._notify(
                f"Cannot {action} income: WRITE mode, capability, and an open Finance period are required."
            )
            return False
        if self._collaboration_manager is not None and not self._collaboration_manager.ensure_write():
            self._notify(f"You must be in WRITE mode to {action} income.")
            return False
        return True

    def _show_add_dialog(self) -> None:
        if not self._ensure_action(Capability.FINANCE_INCOME_CREATE, "add"):
            return
        dialog = IncomeFormDialog(
            self._income_service,
            self._student_service,
            self._class_service,
            initial_payment_date=self._default_transaction_date(),
            parent=self,
        )
        if dialog.exec() == IncomeFormDialog.DialogCode.Accepted:
            self._current_page = 1
            self.refresh()

    def _show_edit_dialog(self, income_id: int) -> None:
        if not self._ensure_action(Capability.FINANCE_INCOME_UPDATE, "edit"):
            return
        dialog = IncomeFormDialog(
            self._income_service,
            self._student_service,
            self._class_service,
            income_id=income_id,
            parent=self,
        )
        if dialog.exec() == IncomeFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_detail_dialog(self, income_id: int) -> None:
        IncomeDetailDialog(self._income_service, income_id, parent=self).exec()

    def _void_income(self, income_id: int) -> None:
        if not self._ensure_action(Capability.FINANCE_INCOME_DELETE, "void"):
            return
        reason, accepted = QInputDialog.getText(
            self,
            "Void khoản thu",
            "Lý do void *:",
        )
        if not accepted:
            return
        reason = reason.strip()
        if not reason:
            QMessageBox.warning(self, "Thiếu lý do", "Vui lòng nhập lý do void.")
            return
        try:
            self._income_service.void_income(income_id, reason)
            self.refresh()
        except Exception as exc:
            logger.exception("Void income failed")
            QMessageBox.critical(self, "Lỗi", str(exc))

    def _delete_income(self, income_id: int) -> None:
        if not self._ensure_action(Capability.FINANCE_INCOME_DELETE, "delete"):
            return
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Khoản thu đã VOID sẽ được ẩn khỏi danh sách thông thường nhưng lịch sử/audit vẫn được giữ. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._income_service.delete_income(income_id)
            self.refresh()
        except Exception as exc:
            logger.exception("Delete income failed")
            QMessageBox.critical(self, "Lỗi", str(exc))

    def _export_csv(self) -> None:
        if self._period_configured is False:
            self._notify("Finance period is not configured.")
            return
        kwargs = self._filter_kwargs()
        if kwargs["date_from"] > kwargs["date_to"]:
            self._notify("Khoảng ngày lọc không hợp lệ.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất Income CSV",
            "income_export.csv",
            "CSV files (*.csv)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"

        try:
            csv_text = self._income_service.export_incomes_csv(
                **kwargs,
                finance_period_start=self._period_start,
                sort_by=self._sort_by,
                ascending=self._sort_ascending,
            )
            Path(filename).write_text(csv_text, encoding="utf-8-sig")
            self._notify("Xuất CSV thành công.", "info")
        except Exception as exc:
            logger.exception("Export income CSV failed")
            QMessageBox.critical(self, "Lỗi xuất CSV", str(exc))

    def _clear_filters(self) -> None:
        previous = [
            self.type_combo.blockSignals(True),
            self.method_combo.blockSignals(True),
            self.status_combo.blockSignals(True),
        ]
        self.search_bar.clear()
        self.type_combo.setCurrentIndex(0)
        self.method_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.type_combo.blockSignals(previous[0])
        self.method_combo.blockSignals(previous[1])
        self.status_combo.blockSignals(previous[2])

        if self._period_start is not None and self._period_end is not None:
            self._reset_date_filters_to_period()
        else:
            self.date_from_edit.setDate(QDate.currentDate().addDays(-30))
            self.date_to_edit.setDate(QDate.currentDate())

        self._current_page = 1
        self._load_page()

    def _apply_action_state(self) -> None:
        self.add_btn.setEnabled(self._can(Capability.FINANCE_INCOME_CREATE))

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._apply_action_state()
