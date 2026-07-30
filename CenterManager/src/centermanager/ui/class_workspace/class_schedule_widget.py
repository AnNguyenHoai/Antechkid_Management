# -*- coding: utf-8 -*-
"""
ClassScheduleWidget - display weekly schedule for a class.
Currently displays sessions, future will support full weekly schedule.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)

from centermanager.services.session_service import SessionService
from centermanager.database.engine import create_production_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class ClassScheduleWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session_service = None
        self._class_id: Optional[int] = None
        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Session", "Date", "Topic"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def set_class(self, class_id: int) -> None:
        self._class_id = class_id
        self._load_sessions()

    def _load_sessions(self) -> None:
        if self._class_id is None:
            self._show_empty()
            return

        try:
            engine = create_production_engine()
            session_factory = sessionmaker(bind=engine)
            self._session_service = SessionService(session_factory)
            sessions = self._session_service.get_sessions_for_class(self._class_id)

            if not sessions:
                self._show_empty()
                return

            self.table.setRowCount(len(sessions))
            for row, sess in enumerate(sessions):
                self.table.setItem(row, 0, QTableWidgetItem(f"#{sess.session_number}"))
                self.table.setItem(row, 1, QTableWidgetItem(sess.scheduled_date.strftime("%d/%m/%Y")))
                self.table.setItem(row, 2, QTableWidgetItem(sess.title))
            self.table.setVisible(True)
        except Exception as e:
            logger.exception("Error loading sessions")
            self._show_empty()

    def _show_empty(self) -> None:
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No sessions scheduled"))
        self.table.setItem(0, 1, QTableWidgetItem(""))
        self.table.setItem(0, 2, QTableWidgetItem(""))
        self.table.setVisible(True)