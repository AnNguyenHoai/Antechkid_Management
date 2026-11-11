# -*- coding: utf-8 -*-
"""
SessionDetailDialog - Teaching Workspace with tabs.
Now includes Attendance Summary in Overview tab.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QSizePolicy, QMessageBox,
    QTabWidget, QGridLayout
)

from centermanager.models.session import Session, SessionStatus
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.attendance_service import AttendanceService
from centermanager.ui.session.session_note_widget import SessionNoteWidget
from centermanager.ui.session.student_highlight_widget import StudentHighlightWidget
from centermanager.ui.session.session_attendance_widget import SessionAttendanceWidget
from centermanager.ui.design_system.tokens import COLORS
from centermanager.ui.design_system.components import SecondaryButton

logger = logging.getLogger(__name__)


class SessionDetailDialog(QDialog):
    """Teaching Workspace for a session with tabs."""
    session_updated = Signal()

    def __init__(
        self,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
        student_service: StudentService,
        class_service: ClassService,
        attendance_service: AttendanceService,
        session_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_service = student_service
        self._class_service = class_service
        self._attendance_service = attendance_service
        self._session_id = session_id
        self._session: Optional[Session] = None
        self._class_id: Optional[int] = None

        self.setWindowTitle("Teaching Workspace")
        self.setMinimumSize(700, 600)
        self.setModal(True)

        self._setup_ui()
        self._load_session()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # ----- Tabs -----
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                padding: 8px 16px;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
                color: #1976d2;
            }
        """)

        # --- Tab 1: Attendance (editing) ---
        self.attendance_widget = SessionAttendanceWidget(
            self._attendance_service,
            self._class_service,
            parent=self
        )
        self.attendance_widget.attendance_changed.connect(self._on_attendance_changed)
        self.tab_widget.addTab(self.attendance_widget, "Attendance")

        # --- Tab 2: Overview (read-only summary + note + highlights) ---
        overview_tab = self._create_overview_tab()
        self.tab_widget.addTab(overview_tab, "Teaching Overview")

        main_layout.addWidget(self.tab_widget)

        # ----- Footer buttons -----
        footer = QHBoxLayout()
        footer.addStretch()

        self.edit_btn = QPushButton("Edit Session")
        self.edit_btn.clicked.connect(self._on_edit_session)
        footer.addWidget(self.edit_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        footer.addWidget(self.close_btn)

        main_layout.addLayout(footer)

        # Set default tab
        self.tab_widget.setCurrentIndex(0)  # Attendance first

    def set_historical_read_only(self, enabled: bool = True) -> None:
        """Archive history is inspectable, never editable from session detail."""
        self.edit_btn.setEnabled(not enabled)
        # These composite widgets contain note/highlight and Attendance write
        # controls. Disabling them leaves their loaded historical content visible
        # while preventing UI-origin mutations and accidental Save actions.
        self.attendance_widget.setEnabled(not enabled)
        self.note_widget.setEnabled(not enabled)
        self.highlight_widget.setEnabled(not enabled)
        if enabled:
            self.setWindowTitle("Teaching History — Read Only")

    def _create_overview_tab(self) -> QWidget:
        """Create the Overview tab containing session info, attendance summary, note and highlights."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Session header
        self.header_widget = self._create_header()
        layout.addWidget(self.header_widget)

        # Divider
        layout.addWidget(self._divider())

        # Attendance Summary (read-only)
        self.attendance_summary_widget = self._create_attendance_summary()
        layout.addWidget(self.attendance_summary_widget)

        # Divider
        layout.addWidget(self._divider())

        # Note section
        self.note_section = self._create_note_section()
        layout.addWidget(self.note_section)

        # Highlights section
        self.highlight_section = self._create_highlight_section()
        layout.addWidget(self.highlight_section)

        # Quick summary (note + highlight counts)
        self.summary_widget = self._create_summary()
        layout.addWidget(self.summary_widget)

        layout.addStretch()
        return tab

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _create_header(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

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

        self.time_label = QLabel()
        self.time_label.setStyleSheet("font-size: 13px; color: #666;")
        info_layout.addWidget(self.time_label)

        layout.addLayout(info_layout)

        stats_layout = QVBoxLayout()
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.status_label = QLabel()
        stats_layout.addWidget(self.status_label)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #666; font-size: 12px;")
        stats_layout.addWidget(self.stats_label)

        layout.addLayout(stats_layout)
        return widget

    def _create_attendance_summary(self) -> QWidget:
        """Read-only attendance summary card."""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        self.att_summary_label = QLabel("Attendance Summary: Loading...")
        self.att_summary_label.setStyleSheet("font-weight: 500;")
        layout.addWidget(self.att_summary_label)

        layout.addStretch()

        self.att_rate_label = QLabel("Rate: --")
        self.att_rate_label.setStyleSheet("font-weight: bold; color: #1976d2;")
        layout.addWidget(self.att_rate_label)

        return widget

    def _create_note_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.note_widget = SessionNoteWidget(
            self._note_service,
            self._session_id,
            parent=self
        )
        self.note_widget.note_saved.connect(self._on_note_changed)
        self.note_widget.dirty_changed.connect(self._update_close_label)
        self.note_widget.note_deleted.connect(self._on_note_changed)
        layout.addWidget(self.note_widget)

        return section

    def _create_highlight_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("⭐ Today's Highlights")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.highlight_widget = StudentHighlightWidget(
            self._highlight_service,
            self._session_id,
            self._student_service,
            self._class_service,
            self._session_service,
            parent=self
        )
        self.highlight_widget.highlight_changed.connect(self._on_highlight_changed)
        layout.addWidget(self.highlight_widget)

        return section

    def _create_summary(self) -> QWidget:
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
        # Refresh is read-only: never save the user's unfinished note.
        if hasattr(self, "note_widget") and self.note_widget.has_pending_changes():
            self.note_widget._set_save_status(
                "Unsaved changes — Save & Close before refreshing"
            )
            return
        try:
            self._session = self._session_service.get_session(self._session_id)
            if not self._session:
                QMessageBox.critical(self, "Error", "Session not found.")
                self.reject()
                return

            self._class_id = self._session.class_id

            # Update header
            self._update_header()

            # Load note and highlights
            self.note_widget._load_note()
            self.highlight_widget._load_highlights()
            self._update_summary()

            # Load attendance for both editing tab and summary
            self.attendance_widget.set_session(self._session_id, self._class_id)
            self._update_attendance_summary()

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
        time_str = ""
        if self._session.start_time and self._session.end_time:
            time_str = f"Time: {self._session.start_time.strftime('%H:%M')} - {self._session.end_time.strftime('%H:%M')}"
        self.time_label.setText(time_str)

        status_text = self._session.status
        color = {
            "Scheduled": "#2196f3",
            "Completed": "#4caf50",
            "Cancelled": "#f44336",
            "Postponed": "#ff9800",
        }.get(status_text, "#999")
        self.status_label.setText(f"Status: {status_text}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_attendance_summary(self) -> None:
        """Update the read-only roster-aware attendance summary in Overview tab."""
        try:
            overview = self._attendance_service.get_session_attendance_overview(self._session_id)
            present = overview.get("Present", 0)
            late = overview.get("Late", 0)
            absent = overview.get("Absent", 0)
            excused = overview.get("Excused", 0)
            unmarked = overview.get("Unmarked", 0)
            rate = overview.get("AttendanceRate", 0.0)

            self.att_summary_label.setText(
                f"Present: {present}  |  Late: {late}  |  Absent: {absent}  |  "
                f"Excused: {excused}  |  Unmarked: {unmarked}"
            )
            self.att_rate_label.setText(f"Rate: {rate:.1f}%")
        except Exception as e:
            logger.exception("Error loading attendance summary")
            self.att_summary_label.setText("Attendance summary unavailable")
            self.att_rate_label.setText("--")

    def _update_summary(self) -> None:
        if not self._session:
            return
        note_exists = self.note_widget._note is not None
        self.note_status_label.setText(f"📝 Note: {'✅ Available' if note_exists else '❌ Not available'}")

        highlights = self.highlight_widget._highlights
        count = len(highlights)
        self.highlight_count_label.setText(f"⭐ Highlights: {count}")

        if self._session.status == SessionStatus.COMPLETED.value:
            self.status_icon_label.setText("✅ Completed")
            self.status_icon_label.setStyleSheet("color: #4caf50;")
        else:
            self.status_icon_label.setText("⏳ Incomplete")
            self.status_icon_label.setStyleSheet("color: #ff9800;")

    def _on_note_changed(self) -> None:
        # SessionNoteWidget already holds the successfully saved record.
        # Avoid a redundant reload that could clear a newer local draft.
        self._update_summary()
        self.session_updated.emit()

    def _on_highlight_changed(self) -> None:
        self._update_summary()
        self.highlight_widget._load_highlights()
        self.session_updated.emit()

    def _on_attendance_changed(self) -> None:
        self._update_attendance_summary()
        self.session_updated.emit()
        # Attendance is persisted independently: a save does not make a
        # Scheduled session billable. Ask separately, only under live WRITE.
        if not self.attendance_widget.isEnabled() or not self.attendance_widget._can_write():
            return
        try:
            current = self._session_service.get_session(self._session_id)
        except Exception:
            logger.exception("Cannot check session status after attendance save")
            return
        if current.status != SessionStatus.SCHEDULED.value:
            self._session = current
            self._update_header()
            return
        from centermanager.core.clock import get_clock
        if (current.actual_date or current.scheduled_date) > get_clock().today():
            return
        answer = QMessageBox.question(
            self,
            "Xác nhận hoàn tất buổi học",
            "Điểm danh đã lưu thành công nhưng Session vẫn là Scheduled.\\n\\n"
            "Buổi học này đã kết thúc thực tế chưa?\\n"
            "Chọn Yes để chuyển sang Completed và cho phép hệ thống tính "
            "học phí theo chính sách Enrollment. Chọn No để giữ Scheduled "
            "và xử lý sau.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self.attendance_widget.isEnabled() or not self.attendance_widget._can_write():
            QMessageBox.warning(self, "READ mode", "WRITE authority is no longer available.")
            return
        try:
            self._session = self._session_service.complete_scheduled_session(self._session_id)
        except Exception as exc:
            logger.exception("Explicit session completion failed")
            QMessageBox.warning(
                self, "Chưa hoàn tất buổi học",
                "Điểm danh đã được lưu. Session chưa được xác nhận Completed.\\n"
                f"Chi tiết: {exc}",
            )
            return
        self._update_header()
        self._update_summary()
        self.attendance_widget.refresh()
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
            self._load_session()
            self.session_updated.emit()

    def refresh(self) -> None:
        self._load_session()

    def _update_close_label(self, _dirty: bool = False) -> None:
        # READ-only history always has a plain Close action.
        self.close_btn.setText(
            "Save & Close"
            if self.note_widget.has_pending_changes() and self.note_widget.isEnabled()
            else "Close"
        )

    def closeEvent(self, event) -> None:
        # Window X must follow the same Save & Close policy as footer Close.
        if self._save_before_closing():
            event.accept()
        else:
            event.ignore()

    def _save_before_closing(self) -> bool:
        if not self.note_widget.flush_pending():
            QMessageBox.warning(
                self, "Teaching Note not saved",
                "The note was not saved. The dialog remains open and your "
                "draft is preserved. Check WRITE access and choose Save & Close again.",
            )
            return False
        return True

    def accept(self) -> None:
        if self._save_before_closing():
            super().accept()

    def reject(self) -> None:
        # Esc follows the same policy; no implicit discard.
        if self._save_before_closing():
            super().reject()
