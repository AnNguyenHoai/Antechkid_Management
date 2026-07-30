# -*- coding: utf-8 -*-
"""
ClassScheduleWidget - display weekly schedule with assessment view.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QMessageBox
)

from centermanager.models.session import Session
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService
from centermanager.ui.session.session_detail_dialog import SessionDetailDialog

logger = logging.getLogger(__name__)


class ClassScheduleWidget(QWidget):
    session_updated = Signal()

    def __init__(
        self,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
        student_service: StudentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_service = student_service
        self._class_id: Optional[int] = None
        self._sessions: List[Session] = []

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Table: Session, Date, Topic, Assessment Status, Actions
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Session", "Date", "Topic", "Assessment", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Schedule")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def set_class(self, class_id: int) -> None:
        self._class_id = class_id
        self._load_sessions()

    def _load_sessions(self) -> None:
        if self._class_id is None:
            self._show_empty()
            return

        try:
            self._sessions = self._session_service.get_sessions_for_class(self._class_id)
            self._update_table()
        except Exception as e:
            logger.exception("Error loading sessions")
            self._show_empty()

    def _update_table(self) -> None:
        self.table.setRowCount(len(self._sessions))
        if not self._sessions:
            self._show_empty()
            return

        for row, sess in enumerate(self._sessions):
            # Session number
            self.table.setItem(row, 0, QTableWidgetItem(f"#{sess.session_number}"))
            # Date
            self.table.setItem(row, 1, QTableWidgetItem(sess.scheduled_date.strftime("%d/%m/%Y")))
            # Topic
            self.table.setItem(row, 2, QTableWidgetItem(sess.title))

            # Assessment status: check if note exists
            note = self._note_service.get_note(sess.id)
            has_highlights = len(self._highlight_service.get_highlights_for_session(sess.id)) > 0
            status_text = "✅ Has assessment" if note else "❌ No assessment"
            if note and has_highlights:
                status_text = "✅ Complete"
            elif note:
                status_text = "📝 Note only"
            elif has_highlights:
                status_text = "⭐ Highlights only"
            self.table.setItem(row, 3, QTableWidgetItem(status_text))

            # Actions: View button
            view_btn = QPushButton("View")
            view_btn.setFixedWidth(60)
            view_btn.clicked.connect(lambda checked, sid=sess.id: self._open_session_detail(sid))
            self.table.setCellWidget(row, 4, view_btn)

        self.table.setVisible(True)

    def _show_empty(self) -> None:
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No sessions scheduled"))
        self.table.setItem(0, 1, QTableWidgetItem(""))
        self.table.setItem(0, 2, QTableWidgetItem(""))
        self.table.setItem(0, 3, QTableWidgetItem(""))
        self.table.setCellWidget(0, 4, None)
        self.table.setVisible(True)

    def _open_session_detail(self, session_id: int) -> None:
        logger.info(f"Opening session detail for session {session_id}")
        try:
            dialog = SessionDetailDialog(
                self._session_service,
                self._note_service,
                self._highlight_service,
                self._student_service,
                session_id,
                parent=self
            )
            if dialog.exec() == SessionDetailDialog.DialogCode.Accepted:
                self._load_sessions()
                self.session_updated.emit()
        except Exception as e:
            logger.exception(f"Error opening session detail: {e}")
            QMessageBox.critical(self, "Error", f"Could not open session: {str(e)}")

    def refresh(self) -> None:
        """External refresh method."""
        if self._class_id:
            self._load_sessions()