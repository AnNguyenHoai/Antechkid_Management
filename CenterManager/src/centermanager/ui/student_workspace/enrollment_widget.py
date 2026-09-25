# -*- coding: utf-8 -*-
"""Student Enrollment UI migrated to Design System V2."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLabel, QVBoxLayout, QWidget

from centermanager.core.clock import get_clock
from centermanager.services.enrollment_service import (
    EnrollmentAlreadyActiveError,
    EnrollmentCapacityError,
    EnrollmentError,
    EnrollmentStatus,
)
from centermanager.services.enrollment_transfer_service import (
    EnrollmentTransferError,
    EnrollmentTransferService,
)
from centermanager.ui.design_system.feedback import ConfirmationDialog, FeedbackController
from centermanager.ui.design_system.form_detail import EditStateBanner
from centermanager.ui.design_system.foundation import Badge, Button, ButtonVariant, Card, Select
from centermanager.ui.design_system.tokens import COLORS, FONT_WEIGHTS, SPACING, TYPOGRAPHY
from centermanager.ui.student_workspace.enrollment_pricing_dialog import EnrollmentPricingDialog


class EnrollmentWidget(QWidget):
    """Student-facing projection of the canonical Enrollment lifecycle."""

    enrollment_changed = Signal()

    def __init__(
        self,
        enrollment_service,
        class_service,
        collaboration_manager,
        parent=None,
        feedback_controller: Optional[FeedbackController] = None,
    ) -> None:
        super().__init__(parent)
        self._enrollment_service = enrollment_service
        self._transfer_service = EnrollmentTransferService.from_enrollment_service(enrollment_service)
        self._class_service = class_service
        self._collaboration_manager = collaboration_manager
        self._feedback = feedback_controller or FeedbackController(self)
        self._student_id: Optional[int] = None
        self._write_enabled = False
        self._build_ui()

    def set_feedback_controller(self, controller: FeedbackController) -> None:
        self._feedback = controller

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["lg"])
        self.edit_state_banner = EditStateBanner("readonly", parent=self)
        layout.addWidget(self.edit_state_banner)
        self.overview_section = Card(
            "Academic summary",
            "Current learning, completed classes, and enrollment history.",
            parent=self,
        )
        overview_wrap = QWidget(self.overview_section)
        self.overview_layout = QHBoxLayout(overview_wrap)
        self.overview_layout.setContentsMargins(0, 0, 0, 0)
        self.overview_layout.setSpacing(SPACING["sm"])
        self.overview_section.add_widget(overview_wrap)
        layout.addWidget(self.overview_section)
        action_card = Card(
            "Enroll in a class",
            "Choose an active class that the student is not currently enrolled in. The same selection is used as the transfer target.",
            parent=self,
        )
        action_wrap = QWidget(action_card)
        action = QHBoxLayout(action_wrap)
        action.setContentsMargins(0, 0, 0, 0)
        action.setSpacing(SPACING["sm"])
        self.class_combo = Select([], parent=action_wrap)
        self.class_combo.setMinimumWidth(280)
        self.class_combo.setAccessibleName("Class to enroll or transfer into")
        self.class_combo.setToolTip("Select an active class for enrollment or transfer")
        self.enroll_btn = Button("Enroll in class", variant=ButtonVariant.PRIMARY, parent=action_wrap)
        self.enroll_btn.clicked.connect(self._enroll_selected)
        action.addWidget(self.class_combo, 1)
        action.addWidget(self.enroll_btn)
        action_card.add_widget(action_wrap)
        layout.addWidget(action_card)
        self.current_section = Card("Current enrollment", parent=self)
        self.current_container = QWidget(self.current_section)
        self.current_layout = QVBoxLayout(self.current_container)
        self.current_layout.setContentsMargins(0, 0, 0, 0)
        self.current_layout.setSpacing(SPACING["sm"])
        self.current_section.add_widget(self.current_container)
        layout.addWidget(self.current_section)
        self.history_section = Card("Academic history", parent=self)
        self.history_container = QWidget(self.history_section)
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(SPACING["sm"])
        self.history_section.add_widget(self.history_container)
        layout.addWidget(self.history_section)
        layout.addStretch()

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        self.refresh()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self.edit_state_banner.set_state("editing" if enabled else "readonly")
        self._update_action_state()

    def refresh(self) -> None:
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
            self._add_message(self.current_layout, "Enrollment history could not be loaded.")
            self._feedback.system_error(
                exc,
                message="Enrollment history could not be loaded.",
                retry_action_id="student-enrollment-refresh",
                key="student-enrollment-load",
            )
            self._update_action_state()
            return
        active = [item for item in history if item.status == EnrollmentStatus.ACTIVE.value]
        completed = [item for item in history if item.status == EnrollmentStatus.COMPLETED.value]
        withdrawn = [item for item in history if item.status == EnrollmentStatus.WITHDRAWN.value]
        past = [item for item in history if item.status != EnrollmentStatus.ACTIVE.value]
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

    def _populate_overview(self, active, completed, withdrawn, history) -> None:
        for label, value in (("Active", len(active)), ("Completed", len(completed)), ("Withdrawn", len(withdrawn)), ("Total records", len(history))):
            metric = Card(parent=self)
            value_label = QLabel(str(value), metric)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet(
                f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['section_title']}px; font-weight: {FONT_WEIGHTS['semibold']};"
            )
            text_label = QLabel(label, metric)
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;")
            metric.add_widget(value_label)
            metric.add_widget(text_label)
            self.overview_layout.addWidget(metric)

    def _reload_classes(self) -> None:
        current = self.class_combo.currentData()
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        self.class_combo.addItem("Select class", None)
        try:
            active_class_ids = set()
            if self._student_id is not None:
                active_class_ids = {
                    item.class_id
                    for item in self._enrollment_service.get_student_history(self._student_id)
                    if item.status == EnrollmentStatus.ACTIVE.value and item.class_id is not None
                }
            for class_obj in self._class_service.list_classes():
                if getattr(class_obj, "status", "ACTIVE") == "ACTIVE" and class_obj.id not in active_class_ids:
                    self.class_combo.addItem(f"{class_obj.name} — {class_obj.course or 'No course'}", class_obj.id)
        except Exception as exc:
            self.class_combo.clear()
            self.class_combo.addItem("Classes unavailable", None)
            self._feedback.system_error(exc, message="Available classes could not be loaded.", key="student-enrollment-classes")
        self.class_combo.blockSignals(False)
        if current is not None:
            index = self.class_combo.findData(current)
            if index >= 0:
                self.class_combo.setCurrentIndex(index)

    def _card(self, enrollment, current: bool) -> Card:
        card = Card(parent=self)
        header = QWidget(card)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        name = QLabel(enrollment.class_name or f"Class #{enrollment.class_id}", header)
        name.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['body']}px; font-weight: {FONT_WEIGHTS['semibold']};"
        )
        header_layout.addWidget(name)
        header_layout.addStretch()
        header_layout.addWidget(Badge.from_status(enrollment.status, parent=header))
        card.add_widget(header)
        metadata = []
        if enrollment.course_name:
            metadata.append(f"Course: {enrollment.course_name}")
        if enrollment.teacher_name:
            metadata.append(f"Teacher: {enrollment.teacher_name}")
        if enrollment.level:
            metadata.append(f"Level: {enrollment.level}")
        if metadata:
            card.add_widget(QLabel(" • ".join(metadata), card))
        dates = []
        if enrollment.start_date:
            dates.append(f"Start: {enrollment.start_date.strftime('%d/%m/%Y')}")
        if enrollment.end_date:
            dates.append(f"End: {enrollment.end_date.strftime('%d/%m/%Y')}")
        if dates:
            card.add_widget(QLabel("   ".join(dates), card))
        duration = self._format_duration(enrollment.start_date, enrollment.end_date, current)
        if duration:
            duration_label = QLabel(duration, card)
            duration_label.setStyleSheet(f"color: {COLORS['text_muted']};")
            card.add_widget(duration_label)
        freezes = list(getattr(enrollment, "freezes", None) or [])
        open_freeze = next((item for item in freezes if item.is_open), None)
        if freezes:
            latest = freezes[-1]
            if open_freeze is not None:
                text = f"Tuition paused from session {open_freeze.start_session} — {open_freeze.reason}"
            else:
                text = f"Latest tuition pause: sessions {latest.start_session}–{latest.end_session}"
            pause_label = QLabel(text, card)
            pause_label.setStyleSheet(f"color: {COLORS['text_muted']};")
            card.add_widget(pause_label)
        if current:
            actions = QWidget(card)
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(SPACING["sm"])
            transfer_btn = Button("Transfer class", variant=ButtonVariant.SECONDARY, parent=actions)
            transfer_btn.setEnabled(self._write_enabled and open_freeze is None)
            transfer_btn.clicked.connect(lambda _=False, item=enrollment: self._transfer(item))
            freeze_btn = Button("Pause tuition", variant=ButtonVariant.SECONDARY, parent=actions)
            freeze_btn.setEnabled(self._write_enabled and open_freeze is None)
            freeze_btn.clicked.connect(lambda _=False, item=enrollment: self._freeze(item))
            resume_btn = Button("Resume tuition", variant=ButtonVariant.SECONDARY, parent=actions)
            resume_btn.setEnabled(self._write_enabled and open_freeze is not None)
            resume_btn.clicked.connect(lambda _=False, item=enrollment, freeze=open_freeze: self._resume(item, freeze))
            complete = Button("Complete", variant=ButtonVariant.SECONDARY, parent=actions)
            complete.setEnabled(self._write_enabled and open_freeze is None)
            complete.clicked.connect(lambda _=False, eid=enrollment.id: self._transition(eid, "complete"))
            withdraw = Button("Withdraw", variant=ButtonVariant.DANGER, parent=actions)
            withdraw.setEnabled(self._write_enabled and open_freeze is None)
            withdraw.clicked.connect(lambda _=False, eid=enrollment.id: self._transition(eid, "withdraw"))
            actions_layout.addWidget(transfer_btn)
            actions_layout.addWidget(freeze_btn)
            actions_layout.addWidget(resume_btn)
            actions_layout.addWidget(complete)
            actions_layout.addWidget(withdraw)
            actions_layout.addStretch()
            card.add_widget(actions)
        return card

    @staticmethod
    def _format_duration(start_date, end_date, current: bool) -> str:
        if not start_date:
            return ""
        end = end_date or get_clock().today()
        days = max((end - start_date).days, 0)
        suffix = "ongoing" if current and end_date is None else "duration"
        return f"{days} day(s) {suffix}"

    def _transfer(self, enrollment) -> None:
        if not self._require_write():
            return
        target_class_id = self.class_combo.currentData()
        if target_class_id is None:
            self._feedback.info("Select the target class above before transferring.", key="student-enrollment")
            return
        try:
            preview = self._transfer_service.preview(enrollment.id, int(target_class_id))
        except EnrollmentTransferError as exc:
            self._feedback.warning(str(exc), title="Transfer unavailable", key="student-enrollment")
            return
        available = float(preview["available_prepaid_credit"])
        credit, ok = QInputDialog.getDouble(
            self,
            "Transfer class",
            f"Prepaid credit to transfer (available {available:,.0f}):",
            available,
            0.0,
            available,
            0,
        )
        if not ok:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Transfer class", "Transfer reason:")
        if not ok:
            return
        try:
            self._transfer_service.transfer(
                enrollment.id,
                int(target_class_id),
                transferred_credit=credit,
                reason=reason,
            )
            self.refresh()
            self.enrollment_changed.emit()
            self._feedback.success("Student transferred to target class", key="student-enrollment")
        except EnrollmentTransferError as exc:
            self._feedback.warning(str(exc), title="Transfer unavailable", key="student-enrollment")
        except Exception as exc:
            self._feedback.system_error(exc, message="The enrollment could not be transferred.", key="student-enrollment")

    def _freeze(self, enrollment) -> None:
        if not self._require_write():
            return
        first = int(enrollment.enrolled_from_session or 1)
        last = int(enrollment.enrolled_until_session or first)
        start, ok = QInputDialog.getInt(
            self,
            "Pause tuition",
            "First session to pause tuition from:",
            first,
            first,
            last,
        )
        if not ok:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Pause tuition", "Reason:")
        if not ok:
            return
        try:
            self._enrollment_service.freeze(enrollment.id, start, reason)
            self.refresh()
            self.enrollment_changed.emit()
            self._feedback.success("Tuition paused", key="student-enrollment")
        except EnrollmentError as exc:
            self._feedback.warning(str(exc), title="Tuition pause unavailable", key="student-enrollment")
        except Exception as exc:
            self._feedback.system_error(exc, message="Tuition could not be paused.", key="student-enrollment")

    def _resume(self, enrollment, freeze) -> None:
        if not self._require_write() or freeze is None:
            return
        last = int(enrollment.enrolled_until_session or freeze.start_session)
        end, ok = QInputDialog.getInt(
            self,
            "Resume tuition",
            "Last session that remains paused:",
            int(freeze.start_session),
            int(freeze.start_session),
            last,
        )
        if not ok:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Resume tuition", "Resume reason:")
        if not ok:
            return
        try:
            self._enrollment_service.resume(enrollment.id, end, reason)
            self.refresh()
            self.enrollment_changed.emit()
            self._feedback.success("Tuition resumed", key="student-enrollment")
        except EnrollmentError as exc:
            self._feedback.warning(str(exc), title="Tuition resume unavailable", key="student-enrollment")
        except Exception as exc:
            self._feedback.system_error(exc, message="Tuition could not be resumed.", key="student-enrollment")

    def _enroll_selected(self) -> None:
        if not self._require_write() or self._student_id is None:
            return
        class_id = self.class_combo.currentData()
        if class_id is None:
            self._feedback.info("Select a class before enrolling the student.", key="student-enrollment")
            return
        pricing = EnrollmentPricingDialog(self._enrollment_service, int(class_id), parent=self)
        if pricing.exec() != QDialog.DialogCode.Accepted:
            return
        operation_id = "student-enrollment-create"
        if not self._feedback.begin_operation(operation_id, "Enrolling student…"):
            return
        try:
            self._enrollment_service.enroll(self._student_id, int(class_id), **pricing.enrollment_kwargs())
            self.refresh()
            self.enrollment_changed.emit()
            self._feedback.finish_operation(operation_id)
            self._feedback.success("Student enrolled", key="student-enrollment")
        except (EnrollmentAlreadyActiveError, EnrollmentCapacityError, EnrollmentError) as exc:
            self._feedback.finish_operation(operation_id)
            self._feedback.warning(str(exc), title="Enrollment unavailable", key="student-enrollment")
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            self._feedback.system_error(exc, message="The student could not be enrolled.", key="student-enrollment")

    def _transition(self, enrollment_id: int, action: str) -> None:
        if not self._require_write():
            return
        verb = "Complete" if action == "complete" else "Withdraw"
        dialog = ConfirmationDialog(
            f"{verb} enrollment",
            f"{verb} this enrollment record?",
            confirm_text=verb,
            dangerous=action == "withdraw",
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        operation_id = f"student-enrollment-{action}-{enrollment_id}"
        if not self._feedback.begin_operation(operation_id, f"{verb}ing enrollment…"):
            return
        try:
            if action == "complete":
                self._enrollment_service.complete(enrollment_id)
                success_text = "Enrollment completed"
            else:
                self._enrollment_service.withdraw(enrollment_id)
                success_text = "Enrollment withdrawn"
            self.refresh()
            self.enrollment_changed.emit()
            self._feedback.finish_operation(operation_id)
            self._feedback.success(success_text, key="student-enrollment")
        except EnrollmentError as exc:
            self._feedback.finish_operation(operation_id)
            self._feedback.warning(str(exc), title="Enrollment unavailable", key="student-enrollment")
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            self._feedback.system_error(exc, message="The enrollment could not be updated.", key="student-enrollment")

    def _require_write(self) -> bool:
        if self._write_enabled:
            return True
        self._feedback.warning(
            "Start editing before changing enrollment.",
            title="Read-only mode",
            key="student-enrollment-write",
        )
        return False

    def _update_action_state(self) -> None:
        has_class = self.class_combo.count() > 0 and self.class_combo.currentData() is not None
        self.class_combo.setEnabled(self._write_enabled)
        self.enroll_btn.setEnabled(self._write_enabled and self._student_id is not None and has_class)

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _add_message(layout, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['body_small']}px;")
        layout.addWidget(label)
