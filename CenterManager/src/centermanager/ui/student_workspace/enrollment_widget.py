# -*- coding: utf-8 -*-
"""Student Enrollment UI: current enrollment + academic history."""
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QFrame, QScrollArea
)

from centermanager.services.enrollment_service import (
    EnrollmentService, EnrollmentStatus, EnrollmentAlreadyActiveError,
    EnrollmentCapacityError, EnrollmentError,
)


class EnrollmentWidget(QWidget):
    """Student-facing projection of the canonical Enrollment lifecycle."""

    enrollment_changed = Signal()

    def __init__(self, enrollment_service, class_service, collaboration_manager, parent=None):
        super().__init__(parent)
        self._enrollment_service = enrollment_service
        self._class_service = class_service
        self._collaboration_manager = collaboration_manager
        self._student_id: Optional[int] = None
        self._write_enabled = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("🎓 Academic Overview")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel("Current learning, completed classes, and enrollment history.")
        subtitle.setStyleSheet("color: #777;")
        layout.addWidget(subtitle)

        self.overview_section = self._make_section("Academic Summary")
        self.overview_layout = QHBoxLayout()
        self.overview_layout.setSpacing(10)
        self.overview_section.layout().addLayout(self.overview_layout)
        layout.addWidget(self.overview_section)

        # Enroll action
        action = QHBoxLayout()
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(280)
        self.class_combo.setToolTip("Select an active class to enroll this student")
        self.enroll_btn = QPushButton("+ Enroll in Class")
        self.enroll_btn.clicked.connect(self._enroll_selected)
        action.addWidget(self.class_combo)
        action.addWidget(self.enroll_btn)
        action.addStretch()
        layout.addLayout(action)

        self.current_section = self._make_section("Current Enrollment")
        self.current_layout = QVBoxLayout()
        self.current_layout.setSpacing(8)
        self.current_section.layout().addLayout(self.current_layout)
        layout.addWidget(self.current_section)

        self.history_section = self._make_section("Academic History")
        self.history_layout = QVBoxLayout()
        self.history_layout.setSpacing(8)
        self.history_section.layout().addLayout(self.history_layout)
        layout.addWidget(self.history_section)
        layout.addStretch()

    def _make_section(self, title):
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        label = QLabel(title)
        label.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(label)
        return box

    def set_student(self, student_id: int):
        self._student_id = student_id
        self.refresh()

    def set_write_enabled(self, enabled: bool):
        self._write_enabled = bool(enabled)
        self._update_action_state()

    def refresh(self):
        self._clear(self.overview_layout)
        self._clear(self.current_layout)
        self._clear(self.history_layout)
        self._reload_classes()
        if self._student_id is None:
            self._update_action_state()
            return

        try:
            history = self._enrollment_service.get_student_history(self._student_id)
        except Exception as exc:
            self._add_message(self.current_layout, f"Unable to load enrollment: {exc}")
            self._update_action_state()
            return

        active = [e for e in history if e.status == EnrollmentStatus.ACTIVE.value]
        completed = [e for e in history if e.status == EnrollmentStatus.COMPLETED.value]
        withdrawn = [e for e in history if e.status == EnrollmentStatus.WITHDRAWN.value]
        past = [e for e in history if e.status != EnrollmentStatus.ACTIVE.value]

        self._populate_overview(active, completed, withdrawn, history)

        if active:
            for enrollment in active:
                self.current_layout.addWidget(self._card(enrollment, current=True))
        else:
            self._add_message(self.current_layout, "No active enrollment.")

        if past:
            for enrollment in past:
                self.history_layout.addWidget(self._card(enrollment, current=False))
        else:
            self._add_message(self.history_layout, "No academic history yet.")

        self._update_action_state()

    def _populate_overview(self, active, completed, withdrawn, history):
        cards = [
            ("Active", len(active)),
            ("Completed", len(completed)),
            ("Withdrawn", len(withdrawn)),
            ("Total Records", len(history)),
        ]
        for label, value in cards:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet(
                "QFrame { background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            value_label = QLabel(str(value))
            value_label.setStyleSheet("font-size: 20px; font-weight: 600;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_label = QLabel(label)
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_label.setStyleSheet("color: #666;")
            card_layout.addWidget(value_label)
            card_layout.addWidget(text_label)
            self.overview_layout.addWidget(card)

    def _reload_classes(self):
        current = self.class_combo.currentData()
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        try:
            active_class_ids = set()
            if self._student_id is not None:
                active_class_ids = {
                    e.class_id for e in self._enrollment_service.get_student_history(self._student_id)
                    if e.status == EnrollmentStatus.ACTIVE.value and e.class_id is not None
                }
            for class_obj in self._class_service.list_classes():
                if (
                    getattr(class_obj, "status", "ACTIVE") == "ACTIVE"
                    and class_obj.id not in active_class_ids
                ):
                    label = f"{class_obj.name} — {class_obj.course or 'No course'}"
                    self.class_combo.addItem(label, class_obj.id)
        except Exception:
            self.class_combo.addItem("Unable to load classes", None)
        self.class_combo.blockSignals(False)
        if current is not None:
            index = self.class_combo.findData(current)
            if index >= 0:
                self.class_combo.setCurrentIndex(index)

    def _card(self, enrollment, current: bool):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        name = QLabel(enrollment.class_name or f"Class #{enrollment.class_id}")
        name.setStyleSheet("font-weight: 600;")
        header.addWidget(name)
        header.addStretch()

        status = QLabel(enrollment.status)
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setMinimumWidth(92)
        status.setStyleSheet(self._status_style(enrollment.status))
        header.addWidget(status)
        layout.addLayout(header)

        metadata = []
        if enrollment.course_name:
            metadata.append(f"Course: {enrollment.course_name}")
        if enrollment.teacher_name:
            metadata.append(f"Teacher: {enrollment.teacher_name}")
        if enrollment.level:
            metadata.append(f"Level: {enrollment.level}")
        if metadata:
            layout.addWidget(QLabel(" • ".join(metadata)))

        dates = []
        if enrollment.start_date:
            dates.append(f"Start: {enrollment.start_date.strftime('%d/%m/%Y')}")
        if enrollment.end_date:
            dates.append(f"End: {enrollment.end_date.strftime('%d/%m/%Y')}")
        if dates:
            layout.addWidget(QLabel("   ".join(dates)))

        duration = self._format_duration(enrollment.start_date, enrollment.end_date, current)
        if duration:
            duration_label = QLabel(duration)
            duration_label.setStyleSheet("color: #666;")
            layout.addWidget(duration_label)

        if current:
            buttons = QHBoxLayout()
            complete = QPushButton("Complete")
            complete.setEnabled(self._write_enabled)
            complete.clicked.connect(
                lambda _=False, eid=enrollment.id: self._transition(eid, "complete")
            )
            withdraw = QPushButton("Withdraw")
            withdraw.setEnabled(self._write_enabled)
            withdraw.clicked.connect(
                lambda _=False, eid=enrollment.id: self._transition(eid, "withdraw")
            )
            buttons.addWidget(complete)
            buttons.addWidget(withdraw)
            buttons.addStretch()
            layout.addLayout(buttons)
        return card

    @staticmethod
    def _status_style(status: str) -> str:
        return (
            "font-weight: 600; padding: 3px 8px; border-radius: 9px; "
            "background: #e8eef5; color: #2f4f6f;"
        )

    @staticmethod
    def _format_duration(start_date, end_date, current: bool) -> str:
        if not start_date:
            return ""
        end = end_date or date.today()
        days = max((end - start_date).days, 0)
        suffix = "ongoing" if current and end_date is None else "duration"
        return f"{days} day(s) {suffix}"

    def _enroll_selected(self):
        if not self._require_write() or self._student_id is None:
            return
        class_id = self.class_combo.currentData()
        if class_id is None:
            return
        try:
            self._enrollment_service.enroll(self._student_id, int(class_id))
            self.refresh()
            self.enrollment_changed.emit()
        except (EnrollmentAlreadyActiveError, EnrollmentCapacityError, EnrollmentError) as exc:
            QMessageBox.warning(self, "Enrollment", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Enrollment Error", str(exc))

    def _transition(self, enrollment_id: int, action: str):
        if not self._require_write():
            return
        try:
            if action == "complete":
                self._enrollment_service.complete(enrollment_id)
            else:
                self._enrollment_service.withdraw(enrollment_id)
            self.refresh()
            self.enrollment_changed.emit()
        except EnrollmentError as exc:
            QMessageBox.warning(self, "Enrollment", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Enrollment Error", str(exc))

    def _require_write(self):
        if self._write_enabled:
            return True
        QMessageBox.warning(self, "Read mode", "Start Editing before changing enrollment.")
        return False

    def _update_action_state(self):
        has_class = self.class_combo.count() > 0 and self.class_combo.currentData() is not None
        self.class_combo.setEnabled(self._write_enabled)
        self.enroll_btn.setEnabled(self._write_enabled and self._student_id is not None and has_class)

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _add_message(layout, text):
        label = QLabel(text)
        label.setStyleSheet("color: #777;")
        layout.addWidget(label)
