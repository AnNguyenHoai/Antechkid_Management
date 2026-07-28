# -*- coding: utf-8 -*-
"""
SessionCard - displays a session in a list.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton

from centermanager.models.session import Session


class SessionCard(QFrame):
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    view_clicked = Signal(int)

    def __init__(self, session: Session, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session = session
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                background: white;
                padding: 6px 10px;
                margin: 2px 0;
            }
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        # Header: number + title + status
        header = QHBoxLayout()
        number_label = QLabel(f"Session {self._session.session_number}")
        number_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(number_label)

        title_label = QLabel(self._session.title)
        title_label.setStyleSheet("font-size: 13px;")
        header.addWidget(title_label)

        header.addStretch()

        status_label = QLabel(self._session.status)
        status_label.setStyleSheet(self._get_status_style(self._session.status))
        header.addWidget(status_label)

        layout.addLayout(header)

        # Info row: date, topic
        info = QHBoxLayout()
        date_str = self._session.scheduled_date.strftime("%d/%m/%Y")
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #666; font-size: 12px;")
        info.addWidget(date_label)

        if self._session.lesson_topic:
            topic_label = QLabel(f"Topic: {self._session.lesson_topic}")
            topic_label.setStyleSheet("color: #555; font-size: 12px;")
            info.addWidget(topic_label)

        info.addStretch()
        layout.addLayout(info)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        view_btn = QPushButton("View")
        view_btn.setFixedWidth(60)
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedWidth(60)
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedWidth(60)
        delete_btn.setStyleSheet("color: #d32f2f;")
        btn_layout.addWidget(view_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        view_btn.clicked.connect(lambda: self.view_clicked.emit(self._session.id))
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._session.id))
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._session.id))

    def _get_status_style(self, status: str) -> str:
        colors = {
            "Scheduled": "#2196f3",
            "Completed": "#4caf50",
            "Cancelled": "#f44336",
            "Postponed": "#ff9800",
        }
        color = colors.get(status, "#999")
        return f"""
            color: {color};
            font-weight: bold;
            font-size: 12px;
            background-color: {color}22;
            padding: 2px 6px;
            border-radius: 3px;
        """