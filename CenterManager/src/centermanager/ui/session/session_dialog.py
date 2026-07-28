# -*- coding: utf-8 -*-
"""
Dialog for adding/editing a session.
"""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QPushButton, QHBoxLayout, QMessageBox
)

from centermanager.models.session import SessionStatus
from centermanager.services.session_service import SessionService, SessionValidationError

logger = logging.getLogger(__name__)


class SessionDialog(QDialog):
    def __init__(
        self,
        session_service: SessionService,
        class_id: int,
        session_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = session_service
        self._class_id = class_id
        self._session_id = session_id
        self._is_edit = session_id is not None

        self.setWindowTitle("Edit Session" if self._is_edit else "Add Session")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_session()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Session title")
        form.addRow("Title *", self.title_edit)

        # Lesson Topic
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("Lesson topic (optional)")
        form.addRow("Lesson Topic", self.topic_edit)

        # Scheduled Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Scheduled Date *", self.date_edit)

        # Actual Date (optional)
        self.actual_date_edit = QDateEdit()
        self.actual_date_edit.setCalendarPopup(True)
        self.actual_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.actual_date_edit.setDate(QDate.currentDate())
        self.actual_date_edit.setSpecialValueText("")
        form.addRow("Actual Date", self.actual_date_edit)

        # Status
        self.status_combo = QComboBox()
        for s in SessionStatus.choices():
            self.status_combo.addItem(s)
        form.addRow("Status", self.status_combo)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_session(self) -> None:
        try:
            session = self._service.get_session(self._session_id)
            self.title_edit.setText(session.title)
            self.topic_edit.setText(session.lesson_topic or "")
            qdate = QDate(session.scheduled_date.year, session.scheduled_date.month, session.scheduled_date.day)
            self.date_edit.setDate(qdate)
            if session.actual_date:
                qdate2 = QDate(session.actual_date.year, session.actual_date.month, session.actual_date.day)
                self.actual_date_edit.setDate(qdate2)
            else:
                self.actual_date_edit.setDate(QDate(2000, 1, 1))
            idx = self.status_combo.findText(session.status)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        except Exception as e:
            logger.exception("Error loading session")
            QMessageBox.critical(self, "Error", "Could not load session data.")
            self.reject()

    def _save(self) -> None:
        title = self.title_edit.text().strip()
        topic = self.topic_edit.text().strip() or None
        scheduled_date = self.date_edit.date().toPython()
        actual_date = self.actual_date_edit.date().toPython() if self.actual_date_edit.date().isValid() else None
        status = self.status_combo.currentText()

        try:
            if self._is_edit:
                self._service.update_session(
                    session_id=self._session_id,
                    title=title,
                    lesson_topic=topic,
                    scheduled_date=scheduled_date,
                    actual_date=actual_date,
                    status=status,
                )
            else:
                self._service.create_session(
                    class_id=self._class_id,
                    title=title,
                    lesson_topic=topic,
                    scheduled_date=scheduled_date,
                    actual_date=actual_date,
                    status=status,
                )
            self.accept()
        except SessionValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving session")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")