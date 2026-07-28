# -*- coding: utf-8 -*-
"""
SessionList - widget displaying sessions for a class.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame
)

from centermanager.models.session import Session
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService
from centermanager.ui.session.session_card import SessionCard
from centermanager.ui.session.session_dialog import SessionDialog
from centermanager.ui.session.session_detail_dialog import SessionDetailDialog

logger = logging.getLogger(__name__)


class SessionList(QWidget):
    session_changed = Signal()

    def __init__(
        self,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
        student_service: StudentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_service = student_service
        self._class_id: Optional[int] = None
        self._sessions: List[Session] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header with add button
        header = QHBoxLayout()
        title = QLabel("📚 Sessions")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.add_btn = QPushButton("+ New Session")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Scroll area for sessions
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(6)
        self.container_layout.setContentsMargins(0, 4, 0, 0)
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

        self._show_empty()

    def _show_empty(self) -> None:
        self._clear_container()
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)
        icon = QLabel("📚")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px;")
        msg = QLabel("No sessions yet.\nCreate your first session.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("color: #999; font-size: 14px;")
        empty_layout.addWidget(icon)
        empty_layout.addWidget(msg)
        self.container_layout.addWidget(empty_widget)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_class(self, class_id: int) -> None:
        """Load sessions for a class."""
        self._class_id = class_id
        self._load_data()

    def _load_data(self) -> None:
        if self._class_id is None:
            return
        try:
            self._sessions = self._service.get_sessions_for_class(self._class_id)
        except Exception as e:
            logger.exception("Error loading sessions")
            self._sessions = []
        self._update_ui()

    def _update_ui(self) -> None:
        self._clear_container()
        if not self._sessions:
            self._show_empty()
            return

        for session in self._sessions:
            card = SessionCard(session)
            card.view_clicked.connect(self._on_view)
            card.edit_clicked.connect(self._on_edit)
            card.delete_clicked.connect(self._on_delete)
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()

    def _on_add(self) -> None:
        if self._class_id is None:
            return
        dialog = SessionDialog(self._service, self._class_id, parent=self)
        if dialog.exec() == SessionDialog.DialogCode.Accepted:
            self._load_data()
            self.session_changed.emit()

    def _on_view(self, session_id: int) -> None:
        dialog = SessionDetailDialog(
            self._service,
            self._note_service,
            self._highlight_service,
            self._student_service,
            session_id,
            parent=self
        )
        if dialog.exec() == SessionDetailDialog.DialogCode.Accepted:
            self._load_data()
            self.session_changed.emit()

    def _on_edit(self, session_id: int) -> None:
        dialog = SessionDialog(self._service, self._class_id, session_id=session_id, parent=self)
        if dialog.exec() == SessionDialog.DialogCode.Accepted:
            self._load_data()
            self.session_changed.emit()

    def _on_delete(self, session_id: int) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this session? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_session(session_id)
                self._load_data()
                self.session_changed.emit()
            except Exception as e:
                logger.exception("Error deleting session")
                QMessageBox.critical(self, "Error", "Could not delete session.")