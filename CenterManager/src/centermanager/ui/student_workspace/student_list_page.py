# -*- coding: utf-8 -*-
"""
StudentListPage - page that displays student list with search, filter, add.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy, QScrollArea
)

from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.design_system import (
    Avatar, SearchBar, EmptyState, PrimaryButton, SecondaryButton,
    FilterBar, Breadcrumb
)
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.students.student_filter_dialog import StudentFilterDialog
from centermanager.ui.students.student_import_dialog import StudentImportDialog
from centermanager.services.student_import_service import StudentImportService
from centermanager.services.student_export_service import StudentExportService
from centermanager.ui import styles

logger = logging.getLogger(__name__)


class StudentListItem(QFrame):
    def __init__(self, student: Student, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._student = student
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border-bottom: 1px solid #f0f0f0;
                padding: 2px 6px;
            }
            QFrame:hover {
                background: #f8f9fa;
            }
        """)
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        avatar = Avatar(self._student.full_name, size=28)
        avatar.setFixedSize(28, 28)
        layout.addWidget(avatar)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        info_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(self._student.full_name)
        name_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        name_label.setWordWrap(False)
        info_layout.addWidget(name_label)

        code_label = QLabel(self._student.student_code)
        code_label.setStyleSheet("font-size: 11px; color: #888;")
        info_layout.addWidget(code_label)

        layout.addLayout(info_layout, 1)

        status = self._student.status or "ACTIVE"
        color = "#4caf50" if status == "ACTIVE" else "#ff9800"
        status_label = QLabel(status)
        status_label.setStyleSheet(f"""
            background: {color}22;
            color: {color};
            padding: 0px 6px;
            border-radius: 8px;
            font-size: 10px;
            font-weight: 500;
        """)
        status_label.setFixedHeight(18)
        layout.addWidget(status_label)

        if self._student.updated_at:
            time_label = QLabel(self._student.updated_at.strftime("%d/%m/%Y"))
            time_label.setStyleSheet("font-size: 10px; color: #aaa;")
            layout.addWidget(time_label)

    @property
    def student(self) -> Student:
        return self._student


class StudentListPage(QWidget):
    student_selected = Signal(int)
    filter_clicked = Signal()
    data_updated = Signal()

    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        assessment_service: AssessmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._parent_service = parent_service
        self._assessment_service = assessment_service
        self._students: List[Student] = []
        self._filtered: List[Student] = []
        self._import_service = StudentImportService(student_service)
        self._export_service = StudentExportService(student_service)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background: white; padding: 6px 10px; border-bottom: 1px solid #e8e8e8;")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.search_bar = SearchBar()
        self.search_bar.text_changed.connect(self._filter)
        top_row.addWidget(self.search_bar)

        self.filter_btn = SecondaryButton("🔍 Filter")
        self.filter_btn.clicked.connect(self.filter_clicked.emit)
        top_row.addWidget(self.filter_btn)

        self.add_btn = PrimaryButton("+ Add")
        self.add_btn.clicked.connect(self.show_add_dialog)
        top_row.addWidget(self.add_btn)

        toolbar_layout.addLayout(top_row)

        self.filter_bar = FilterBar([
            {"key": "status", "label": "Status", "type": "combo", "options": ["Active", "Archived"]},
            {"key": "enrollment", "label": "Enrollment", "type": "combo", "options": ["Enrolled", "Not Enrolled"]},
            {"key": "assessment", "label": "Assessment", "type": "combo", "options": ["Has Assessment", "No Assessment"]},
        ])
        self.filter_bar.filter_changed.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.filter_bar)

        layout.addWidget(toolbar)

        self.count_label = QLabel("0 students")
        self.count_label.setStyleSheet("padding: 2px 10px; font-size: 12px; color: #888;")
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                outline: none;
                background: white;
            }
            QListWidget::item {
                padding: 0px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
            }
        """)
        self.list_widget.setSpacing(0)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self.empty_widget = EmptyState(
            icon="👤",
            title="No students found",
            description="Try adjusting your search or filter."
        )
        self.empty_widget.setVisible(False)
        layout.addWidget(self.empty_widget)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.list_widget.itemWidget(item)
        if widget and hasattr(widget, 'student'):
            self.student_selected.emit(widget.student.id)

    def _on_filter_changed(self, filters: dict) -> None:
        self._apply_filters(filters)

    def _apply_filters(self, filters: dict) -> None:
        self._filter(self.search_bar.text())

    def refresh(self) -> None:
        try:
            self._students = self._student_service.list_students()
        except Exception as e:
            logger.exception("Failed to load students")
            self._students = []
        self._filter(self.search_bar.text())

    def _filter(self, text: str) -> None:
        if not text.strip():
            self._filtered = self._students[:]
        else:
            if len(text.strip()) > 2:
                try:
                    self._filtered = self._student_service.search_students(text.strip())
                except Exception as e:
                    logger.exception("Search failed")
                    self._filtered = self._students[:]
            else:
                lower = text.strip().lower()
                self._filtered = [
                    s for s in self._students
                    if lower in s.student_code.lower() or lower in s.full_name.lower()
                ]
        self._populate_list()

    def _populate_list(self) -> None:
        self.list_widget.clear()
        self.count_label.setText(f"{len(self._filtered)} students")

        if not self._filtered:
            self.list_widget.setVisible(False)
            self.empty_widget.setVisible(True)
            return

        self.list_widget.setVisible(True)
        self.empty_widget.setVisible(False)

        for student in self._filtered:
            item = QListWidgetItem()
            widget = StudentListItem(student)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def show_add_dialog(self) -> None:
        dialog = StudentFormDialog(self._student_service, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()
            self.data_updated.emit()  # instead of student_selected.emit(-1)

    def export_students(self) -> None:
        try:
            file_path = self._export_service.export_all_active()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Export", f"Exported to: {file_path}")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", str(e))

    def show_filter_dialog(self) -> None:
        dialog = StudentFilterDialog(parent=self)
        if dialog.exec() == StudentFilterDialog.DialogCode.Accepted:
            filter_criteria = dialog.get_filter()
            if filter_criteria:
                from centermanager.services.student_filter_service import StudentFilterService
                from centermanager.database.engine import create_production_engine
                from sqlalchemy.orm import sessionmaker
                engine = create_production_engine()
                session_factory = sessionmaker(bind=engine)
                filter_service = StudentFilterService(session_factory)
                try:
                    self._filtered = filter_service.filter_students(filter_criteria)
                    self._populate_list()
                except Exception as e:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.critical(self, "Filter Error", str(e))