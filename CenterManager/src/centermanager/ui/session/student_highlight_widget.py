# -*- coding: utf-8 -*-
"""
StudentHighlightWidget - Compact UI for adding/viewing student highlights.
Each highlight occupies only one line.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QMessageBox, QSizePolicy
)

from centermanager.models.student_highlight import HighlightType, StudentHighlight
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService

logger = logging.getLogger(__name__)


class StudentHighlightWidget(QWidget):
    highlight_changed = Signal()

    def __init__(
        self,
        highlight_service: StudentHighlightService,
        session_id: int,
        student_service: StudentService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = highlight_service
        self._session_id = session_id
        self._student_service = student_service
        self._highlights: List[StudentHighlight] = []
        self._setup_ui()
        self._load_highlights()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ---- Add form (1 row) ----
        form_row = QHBoxLayout()
        form_row.setSpacing(6)

        self.student_combo = QComboBox()
        self.student_combo.setMinimumWidth(150)
        self._load_students()
        form_row.addWidget(self.student_combo)

        self.type_combo = QComboBox()
        for t in HighlightType.choices():
            self.type_combo.addItem(HighlightType.display_name(t), t)
        form_row.addWidget(self.type_combo)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title")
        self.title_edit.setMinimumWidth(120)
        form_row.addWidget(self.title_edit)

        self.add_btn = QPushButton("Add")
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self._add_highlight)
        form_row.addWidget(self.add_btn)

        layout.addLayout(form_row)

        # ---- List of highlights ----
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                padding: 0px;
            }
        """)
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.list_widget)

    def _load_students(self) -> None:
        try:
            students = self._student_service.list_students()
            self.student_combo.clear()
            for s in students:
                self.student_combo.addItem(f"{s.full_name} ({s.student_code})", s.id)
        except Exception as e:
            logger.exception("Error loading students")

    def _load_highlights(self) -> None:
        try:
            self._highlights = self._service.get_highlights_for_session(self._session_id)
        except Exception as e:
            logger.exception("Error loading highlights")
            self._highlights = []
        self._update_list()

    def _update_list(self) -> None:
        self.list_widget.clear()
        if not self._highlights:
            # Empty state (inline)
            empty_item = QListWidgetItem("No highlights yet")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(empty_item)
            return

        for h in self._highlights:
            item = QListWidgetItem()
            item.setSizeHint(self._create_item_widget(h).sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, self._create_item_widget(h))

    def _create_item_widget(self, highlight: StudentHighlight) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: transparent;
                padding: 2px 0;
            }
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Icon based on type
        icon_map = {
            "POSITIVE": "🌟",
            "SUPPORT": "🆘",
            "NEUTRAL": "📋",
        }
        icon_label = QLabel(icon_map.get(highlight.type, "📌"))
        icon_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(icon_label)

        # Student name
        name = highlight.student.full_name if highlight.student else "Unknown"
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: 500; font-size: 13px;")
        layout.addWidget(name_label)

        # Title (short)
        title_label = QLabel(highlight.title)
        title_label.setStyleSheet("font-size: 13px; color: #333;")
        title_label.setWordWrap(False)
        layout.addWidget(title_label)

        layout.addStretch()

        # Delete button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #999;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #d32f2f;
            }
        """)
        del_btn.clicked.connect(lambda: self._delete_highlight(highlight.id))
        layout.addWidget(del_btn)

        # Tooltip with description if any
        if highlight.description:
            widget.setToolTip(highlight.description)

        return widget

    def _add_highlight(self) -> None:
        student_id = self.student_combo.currentData()
        highlight_type = self.type_combo.currentData()
        title = self.title_edit.text().strip()

        if not student_id:
            QMessageBox.warning(self, "Error", "Please select a student.")
            return
        if not highlight_type:
            QMessageBox.warning(self, "Error", "Please select a type.")
            return
        if not title:
            QMessageBox.warning(self, "Error", "Title is required.")
            return

        try:
            self._service.create_highlight(
                session_id=self._session_id,
                student_id=student_id,
                highlight_type=highlight_type,
                title=title,
                description=None,  # optional, can be added later
            )
            self.title_edit.clear()
            self._load_highlights()
            self.highlight_changed.emit()
        except Exception as e:
            logger.exception("Error adding highlight")
            QMessageBox.critical(self, "Error", str(e))

    def _delete_highlight(self, highlight_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this highlight?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_highlight(highlight_id)
                self._load_highlights()
                self.highlight_changed.emit()
            except Exception as e:
                logger.exception("Error deleting highlight")
                QMessageBox.critical(self, "Error", str(e))