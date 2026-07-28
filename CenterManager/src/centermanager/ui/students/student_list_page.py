# -*- coding: utf-8 -*-
"""
Student list page widget.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QHeaderView,
    QAbstractItemView,
)

from centermanager.services.student_service import StudentService
from centermanager.models.student import Student
from centermanager.ui.students.helpers import calculate_age, format_age_for_display
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.students.student_profile_dialog import StudentProfileDialog

logger = logging.getLogger(__name__)


class StudentListPage(QWidget):
    """Main page for listing students."""

    def __init__(self, student_service: StudentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = student_service
        self._students: List[Student] = []
        self._filtered_students: List[Student] = []

        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Code or Name...")
        top_bar.addWidget(self.search_input)

        top_bar.addStretch()

        self.add_button = QPushButton("+ Add Student")
        self.add_button.setFixedHeight(30)
        top_bar.addWidget(self.add_button)

        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Age", "Level", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.table.doubleClicked.connect(self._on_row_double_clicked)

    def _on_search_text_changed(self, text: str) -> None:
        self._apply_filter(text)

    def _on_add_clicked(self) -> None:
        dialog = StudentFormDialog(self._service, self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()

    def _on_row_double_clicked(self, index) -> None:
        row = index.row()
        if row < 0 or row >= len(self._filtered_students):
            return
        student = self._filtered_students[row]
        dialog = StudentProfileDialog(self._service, student.id, self)
        dialog.exec()

    def refresh(self) -> None:
        try:
            self._students = self._service.list_students()
            self.status_label.setText(f"Loaded {len(self._students)} students")
            self._apply_filter(self.search_input.text())
        except Exception:
            logger.exception("Failed to refresh student list")
            self.status_label.setText("Unable to load students.")
            self._students = []
            self._filtered_students = []
            self._update_table()

    def _apply_filter(self, text: str) -> None:
        if not text.strip():
            self._filtered_students = self._students[:]
        else:
            lower = text.strip().lower()
            self._filtered_students = [
                s for s in self._students
                if lower in s.student_code.lower() or lower in s.full_name.lower()
            ]
        self._update_table()

    def _update_table(self) -> None:
        self.table.setRowCount(len(self._filtered_students))
        for row, student in enumerate(self._filtered_students):
            age = calculate_age(student.date_of_birth)
            age_str = format_age_for_display(age)

            self.table.setItem(row, 0, QTableWidgetItem(student.student_code))
            self.table.setItem(row, 1, QTableWidgetItem(student.full_name))
            self.table.setItem(row, 2, QTableWidgetItem(age_str))
            self.table.setItem(row, 3, QTableWidgetItem(student.current_level or ""))
            self.table.setItem(row, 4, QTableWidgetItem(student.status or ""))