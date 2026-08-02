# -*- coding: utf-8 -*-
"""
SessionDetailDialog - Teaching Workspace.
Displays session information, teaching note, and student highlights in one screen.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QSizePolicy, QMessageBox
)

from centermanager.models.session import Session, SessionStatus
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService
from centermanager.ui.session.session_note_widget import SessionNoteWidget
from centermanager.ui.session.student_highlight_widget import StudentHighlightWidget

logger = logging.getLogger(__name__)


class SessionDetailDialog(QDialog):
    """Teaching Workspace for a session."""
    session_updated = Signal()

    def __init__(
        self,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
        student_service: StudentService,
        session_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_service = student_service
        self._session_id = session_id
        self._session: Optional[Session] = None

        self.setWindowTitle("Teaching Workspace")
        self.setMinimumSize(650, 600)
        self.setModal(True)

        self._setup_ui()
        self._load_session()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Scroll area to accommodate all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(16)
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # 1. Session Information Header
        self.header_widget = self._create_header()
        self.container_layout.addWidget(self.header_widget)

        # Divider
        self.container_layout.addWidget(self._divider())

        # 2. Teaching Note Section
        self.note_section = self._create_note_section()
        self.container_layout.addWidget(self.note_section)

        # 3. Today's Highlights Section
        self.highlight_section = self._create_highlight_section()
        self.container_layout.addWidget(self.highlight_section)

        # 4. Quick Summary (at bottom)
        self.summary_widget = self._create_summary()
        self.container_layout.addWidget(self.summary_widget)

        # Buttons at bottom
        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Edit Session")
        self.edit_btn.clicked.connect(self._on_edit_session)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.close_btn)
        self.container_layout.addLayout(btn_layout)

        #highlight connection
        self.highlight_widget.highlight_changed.connect(self._on_highlight_changed)
        
    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _create_header(self) -> QWidget:
        """Session information header."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Left: Title and status
        info_layout = QVBoxLayout()
        self.number_label = QLabel()
        self.number_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        info_layout.addWidget(self.number_label)

        self.topic_label = QLabel()
        self.topic_label.setStyleSheet("font-size: 14px; color: #555;")
        info_layout.addWidget(self.topic_label)

        self.date_label = QLabel()
        self.date_label.setStyleSheet("font-size: 13px; color: #666;")
        info_layout.addWidget(self.date_label)

        layout.addLayout(info_layout)

        # Right: Status + quick stats
        stats_layout = QVBoxLayout()
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.status_label = QLabel()
        stats_layout.addWidget(self.status_label)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #666; font-size: 12px;")
        stats_layout.addWidget(self.stats_label)

        layout.addLayout(stats_layout)
        return widget

    def _create_note_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Không thêm header nữa, vì widget đã có header
        self.note_widget = SessionNoteWidget(
            self._note_service,
            self._session_id,
            parent=self
        )
        self.note_widget.note_saved.connect(self._on_note_changed)
        self.note_widget.note_deleted.connect(self._on_note_changed)
        layout.addWidget(self.note_widget)

        return section

    def _create_highlight_section(self) -> QWidget:
        """Today's Highlights section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with Add button
        header = QHBoxLayout()
        title = QLabel("⭐ Today's Highlights")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Highlight widget
        self.highlight_widget = StudentHighlightWidget(
            self._highlight_service,
            self._session_id,
            self._student_service,
            parent=self
        )
        self.highlight_widget.highlight_changed.connect(self._on_highlight_changed)
        layout.addWidget(self.highlight_widget)

        return section

    def _create_summary(self) -> QWidget:
        """Quick summary at bottom."""
        widget = QWidget()
        widget.setStyleSheet("background-color: #f5f5f5; padding: 6px 12px; border-radius: 4px;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.note_status_label = QLabel("📝 Note: Not available")
        layout.addWidget(self.note_status_label)

        layout.addStretch()

        self.highlight_count_label = QLabel("⭐ Highlights: 0")
        layout.addWidget(self.highlight_count_label)

        layout.addStretch()

        self.status_icon_label = QLabel()
        layout.addWidget(self.status_icon_label)

        return widget

    def _load_session(self) -> None:
        """Load session data and refresh UI."""
        try:
            self._session = self._session_service.get_session(self._session_id)
            if not self._session:
                QMessageBox.critical(self, "Error", "Session not found.")
                self.reject()
                return

            self._update_header()
            # Note widget already loaded via __init__, but we need to refresh after session loaded
            self.note_widget._load_note()  # trigger reload
            self.highlight_widget._load_highlights()
            self._update_summary()
            self._update_note_section_status()

        except Exception as e:
            logger.exception("Error loading session detail")
            QMessageBox.critical(self, "Error", "Could not load session data.")
            self.reject()

    def _update_header(self) -> None:
        if not self._session:
            return
        self.number_label.setText(f"Session #{self._session.session_number}")
        self.topic_label.setText(f"Topic: {self._session.lesson_topic or '—'}")
        self.date_label.setText(f"Scheduled: {self._session.scheduled_date.strftime('%d/%m/%Y')}")
        # Status
        status_text = self._session.status
        color = {
            "Scheduled": "#2196f3",
            "Completed": "#4caf50",
            "Cancelled": "#f44336",
            "Postponed": "#ff9800",
        }.get(status_text, "#999")
        self.status_label.setText(f"Status: {status_text}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_summary(self) -> None:
        if not self._session:
            return
        # Note availability
        note_exists = self.note_widget._note is not None
        self.note_status_label.setText(f"📝 Note: {'✅ Available' if note_exists else '❌ Not available'}")

        # Highlight count
        highlights = self.highlight_widget._highlights
        count = len(highlights)
        self.highlight_count_label.setText(f"⭐ Highlights: {count}")

        # Status icon
        if self._session.status == SessionStatus.COMPLETED.value:
            self.status_icon_label.setText("✅ Completed")
            self.status_icon_label.setStyleSheet("color: #4caf50;")
        else:
            self.status_icon_label.setText("⏳ Incomplete")
            self.status_icon_label.setStyleSheet("color: #ff9800;")

    def _update_note_section_status(self) -> None:
        # Called when note changes to update summary
        self._update_summary()

    def _on_note_changed(self) -> None:
        """Refresh after note save/delete."""
        self._update_summary()
        # Reload note status
        self.note_widget._load_note()
        self._update_note_section_status()
        # Emit signal to refresh parent (session list)
        self.session_updated.emit()

    def _on_highlight_changed(self) -> None:
        """Refresh after highlight changes."""
        self._update_summary()
        self.highlight_widget._load_highlights()
        self.session_updated.emit()

    def _on_edit_session(self) -> None:
        from centermanager.ui.session.session_dialog import SessionDialog
        dialog = SessionDialog(
            self._session_service,
            self._session.class_id,
            session_id=self._session_id,
            parent=self
        )
        if dialog.exec() == SessionDialog.DialogCode.Accepted:
            # Reload session data
            self._load_session()
            self.session_updated.emit()

    def refresh(self) -> None:
        """External refresh method."""
        self._load_session()