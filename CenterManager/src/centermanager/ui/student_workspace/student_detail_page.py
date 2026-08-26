# -*- coding: utf-8 -*-
"""StudentDetailPage - displays full student profile with all sections.
Now with platform integration and write protection.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QTabWidget, QMessageBox
)

from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_note_service import StudentNoteService
from centermanager.services.student_document_service import StudentDocumentService
from centermanager.services.income_service import IncomeService
from centermanager.services.class_service import ClassService
from centermanager.services.enrollment_service import EnrollmentService
from centermanager.services.permission_service import PermissionService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.report_service import ReportService
from centermanager.services.exceptions import StudentNotFoundError
from centermanager.models.student import Student
from centermanager.ui.students.helpers import calculate_age, format_date_for_display
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.parents import ParentCard, ParentDialog
from centermanager.ui.assessment import AssessmentSection
from centermanager.ui.timeline import TimelineWidget
from centermanager.ui.summary import SummaryWidget
from centermanager.ui.student_workspace.profile_widget import ProfileWidget
from centermanager.ui.student_workspace.quick_actions_widget import QuickActionsWidget
from centermanager.ui.student_workspace.notes_widget import NotesWidget
from centermanager.ui.student_workspace.documents_widget import DocumentsWidget
from centermanager.ui.student_workspace.student_financial_widget import StudentFinancialWidget
from centermanager.ui.student_workspace.student_attendance_widget import StudentAttendanceWidget
from centermanager.ui.student_workspace.report_list_widget import ReportListWidget
from centermanager.ui.student_workspace.enrollment_widget import EnrollmentWidget
from centermanager.ui.design_system import (
    SectionHeader, InfoPanel, PrimaryButton, SecondaryButton,
    DangerButton, Breadcrumb, Avatar
)
from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS
from centermanager.ui import styles

from centermanager.platform.context import PlatformContext
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.business import WriteGuard

logger = logging.getLogger(__name__)


class StudentDetailPage(QWidget):
    back_clicked = Signal()
    student_updated = Signal()
    go_to_finance = Signal()

    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        timeline_service: TimelineService,
        assessment_service: AssessmentService,
        summary_service: StudentSummaryService,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
        student_note_service: StudentNoteService,
        document_service: StudentDocumentService,
        income_service: IncomeService,
        class_service: ClassService,
        enrollment_service: EnrollmentService,
        permission_service: PermissionService,
        outstanding_service: OutstandingService,
        attendance_service: AttendanceService,
        report_service: ReportService,
        platform_context: PlatformContext,
        collaboration_manager: CollaborationManager,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._parent_service = parent_service
        self._timeline_service = timeline_service
        self._assessment_service = assessment_service
        self._summary_service = summary_service
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_note_service = student_note_service
        self._document_service = document_service
        self._income_service = income_service
        self._class_service = class_service
        self._enrollment_service = enrollment_service
        self._permission_service = permission_service
        self._outstanding_service = outstanding_service
        self._attendance_service = attendance_service
        self._report_service = report_service
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._write_guard = WriteGuard(collaboration_manager)

        self._current_student_id: Optional[int] = None
        self._current_student: Optional[Student] = None
        self._write_enabled = False
        self._parent_mutation_buttons = []

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar with back button
        top_bar = QWidget()
        top_bar.setStyleSheet(f"""
            background: {COLORS['surface']};
            border-bottom: 1px solid {COLORS['border_light']};
            padding: {SPACING['xs']}px {SPACING['md']}px;
        """)
        top_bar_layout = QHBoxLayout(top_bar)
        self.back_btn = SecondaryButton("← Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        top_bar_layout.addWidget(self.back_btn)
        top_bar_layout.addStretch()
        main_layout.addWidget(top_bar)

        # Main content with tabs
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

        # Tab 1: Student Profile
        self.profile_tab = self._create_profile_tab()
        self.tab_widget.addTab(self.profile_tab, "Profile")

        # Tab 2: Enrollment
        self.enrollment_widget = EnrollmentWidget(
            self._enrollment_service,
            self._class_service,
            self._collaboration_manager,
            parent=self,
        )
        self.enrollment_widget.enrollment_changed.connect(self._on_data_changed)
        self.tab_widget.addTab(self.enrollment_widget, "🎓 Enrollment")

        # Tab 2: Financial
        self.financial_tab = StudentFinancialWidget(
            self._income_service,
            self._student_service,
            self._class_service,
            self._permission_service,
            self._outstanding_service,
            parent=self
        )
        self.financial_tab.open_finance_clicked.connect(self._on_open_finance)
        self.financial_tab.financial_updated.connect(self._on_data_changed)
        self.tab_widget.addTab(self.financial_tab, "💰 Financial")

        # Tab 3: Attendance
        self.attendance_widget = StudentAttendanceWidget(
            self._attendance_service,
            parent=self
        )
        self.tab_widget.addTab(self.attendance_widget, "📋 Attendance")

        # Tab 4: Reports
        self.report_list_widget = ReportListWidget(self._report_service, parent=self)
        self.report_list_widget.report_changed.connect(self._on_data_changed)
        self.tab_widget.addTab(self.report_list_widget, "📄 Báo cáo")

        main_layout.addWidget(self.tab_widget)

    def _create_profile_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SPACING['md'], SPACING['lg'], SPACING['md'], SPACING['lg'])
        container_layout.setSpacing(SPACING['xl'])

        # Quick Actions
        self.quick_actions = QuickActionsWidget()
        self.quick_actions.upload_photo_clicked.connect(self._on_upload_photo)
        container_layout.addWidget(self.quick_actions)

        # Profile
        self.profile_widget = ProfileWidget()
        container_layout.addWidget(self.profile_widget)

        # Summary
        self.summary_widget = SummaryWidget()
        container_layout.addWidget(self.summary_widget)

        # Parents
        self.parents_section = self._create_vertical_section("👨‍👩‍👦 Parents")
        self.parents_container = QWidget()
        self.parents_layout = QVBoxLayout(self.parents_container)
        self.parents_layout.setSpacing(SPACING['sm'])
        self.parents_layout.setContentsMargins(0, 0, 0, 0)
        self.parents_section.layout().addWidget(self.parents_container)
        container_layout.addWidget(self.parents_section)

        # Assessment
        self.assessment_section = AssessmentSection(self._assessment_service)
        self.assessment_section.assessment_changed.connect(self._on_data_changed)
        container_layout.addWidget(self.assessment_section)

        # Timeline
        self.timeline_section = self._create_vertical_section("📅 Timeline")
        self.timeline_widget = TimelineWidget()
        self.timeline_section.layout().addWidget(self.timeline_widget)
        container_layout.addWidget(self.timeline_section)

        # Notes
        self.notes_section = self._create_vertical_section("📝 Notes")
        self.notes_widget = NotesWidget(self._student_note_service)
        self.notes_widget.note_changed.connect(self._on_data_changed)
        self.notes_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.notes_section.layout().addWidget(self.notes_widget)
        container_layout.addWidget(self.notes_section)

        # Documents
        self.documents_section = self._create_vertical_section("📎 Documents")
        self.documents_widget = DocumentsWidget(self._document_service)
        self.documents_widget.document_changed.connect(self._on_data_changed)
        self.documents_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.documents_section.layout().addWidget(self.documents_widget)
        container_layout.addWidget(self.documents_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Connect quick actions
        self.quick_actions.set_actions(
            on_edit=self._on_edit_clicked,
            on_add_parent=self._on_add_parent,
            on_add_assessment=self._on_add_assessment,
            on_add_note=self._on_add_note,
            on_upload_doc=self._on_upload_doc,
            on_export_pdf=self._export_pdf,
            on_upload_photo=self._on_upload_photo,
        )

        return tab

    def _create_vertical_section(self, title: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['xs'])
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title_label)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {COLORS['border_light']}; height: 1px;")
        layout.addWidget(line)
        return section

    def _show_empty(self) -> None:
        self._current_student_id = None
        self._current_student = None
        self.tab_widget.setVisible(False)

    def _show_detail(self) -> None:
        self.tab_widget.setVisible(True)

    def refresh_current_student(self) -> None:
        """Refresh every detail surface from the authoritative student id."""
        if self._current_student_id is None:
            return
        self.load_student(self._current_student_id)

    def load_student(self, student_id: int) -> None:
        try:
            student = self._student_service.get_student(student_id)
        except StudentNotFoundError:
            logger.warning(f"Student {student_id} not found")
            self._show_empty()
            return
        except Exception as e:
            logger.exception(f"Error loading student {student_id}")
            self._show_empty()
            return

        self._current_student_id = student.id
        self._current_student = student
        self._populate_profile(student)
        self.enrollment_widget.set_student(student.id)
        self._populate_financial(student.id)
        self._populate_attendance(student.id)
        self.report_list_widget.set_student(student.id)
        self._show_detail()
        self.set_write_enabled(self._write_enabled)

    def _populate_profile(self, student: Student) -> None:
        # Profile
        parents = self._parent_service.get_parents_for_student(student.id)
        primary = next((p for p in parents if p.is_primary_contact), parents[0] if parents else None)
        primary_name = primary.name if primary else ""
        primary_phone = primary.phone if primary else ""
        self.profile_widget.set_student(student, primary_name, primary_phone)

        # Summary
        summary = self._summary_service.get_summary(student.id)
        self.summary_widget.set_summary(summary)

        # Parents
        self._load_parents(student.id)

        # Assessment
        self.assessment_section.set_student(student.id)

        # Timeline
        events = self._timeline_service.get_student_timeline(student.id)
        self.timeline_widget.set_events(events)

        # Notes
        self.notes_widget.set_student(student.id)

        # Documents
        self.documents_widget.set_student(student.id, student.student_code)

    def _populate_financial(self, student_id: int) -> None:
        self.financial_tab.set_student(student_id)

    def _populate_attendance(self, student_id: int) -> None:
        self.attendance_widget.set_student(student_id)

    def _load_parents(self, student_id: int) -> None:
        self._clear_parents()
        self._parent_mutation_buttons = []
        try:
            parents = self._parent_service.get_parents_for_student(student_id)
        except Exception as e:
            logger.exception("Error loading parents")
            parents = []

        if not parents:
            empty_widget = QWidget()
            empty_layout = QVBoxLayout(empty_widget)
            empty_layout.setContentsMargins(0, SPACING['sm'], 0, SPACING['sm'])
            empty_layout.setSpacing(SPACING['xs'])
            icon = QLabel("👨‍👩‍👧")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_large']}px;")
            empty_layout.addWidget(icon)
            msg = QLabel("No parent information.\nAdd a guardian to this student.")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet(f"""
                color: {COLORS['text_muted']};
                font-size: {TYPOGRAPHY['body']}px;
            """)
            empty_layout.addWidget(msg)
            add_btn = QPushButton("+ Add Parent")
            add_btn.setFixedWidth(120)
            add_btn.setStyleSheet(styles.BUTTON_PRIMARY)
            add_btn.clicked.connect(self._on_add_parent)
            add_btn.setEnabled(self._write_enabled)
            self._parent_mutation_buttons.append(add_btn)
            empty_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self.parents_layout.addWidget(empty_widget)
        else:
            for parent in parents:
                card = ParentCard(parent)
                card.edit_clicked.connect(self._on_edit_parent)
                card.delete_clicked.connect(self._on_delete_parent)
                if hasattr(card, "set_write_enabled"):
                    card.set_write_enabled(self._write_enabled)
                self.parents_layout.addWidget(card)
            add_btn = QPushButton("+ Add Parent")
            add_btn.setFixedWidth(120)
            add_btn.setStyleSheet(styles.BUTTON_PRIMARY)
            add_btn.clicked.connect(self._on_add_parent)
            add_btn.setEnabled(self._write_enabled)
            self._parent_mutation_buttons.append(add_btn)
            self.parents_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _clear_parents(self) -> None:
        self._parent_mutation_buttons = []
        while self.parents_layout.count():
            item = self.parents_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_add_parent(self) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        dialog = ParentDialog(self._parent_service, self._current_student_id, parent_widget=self)
        if dialog.exec() == ParentDialog.DialogCode.Accepted:
            self._on_data_changed()

    def _on_edit_parent(self, parent_id: int) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        dialog = ParentDialog(self._parent_service, self._current_student_id, parent_id=parent_id, parent_widget=self)
        if dialog.exec() == ParentDialog.DialogCode.Accepted:
            self._on_data_changed()

    def _on_delete_parent(self, parent_id: int) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        reply = QMessageBox.question(self, "Confirm Delete", "Delete this parent?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self._parent_service.delete_parent(parent_id)
                self._on_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_add_assessment(self) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        from centermanager.ui.assessment.assessment_dialog import AssessmentDialog
        dialog = AssessmentDialog(self._assessment_service, self._current_student_id, parent=self)
        if dialog.exec() == AssessmentDialog.DialogCode.Accepted:
            self._on_data_changed()

    def _on_add_note(self) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        self.notes_widget._on_add()

    def _on_upload_doc(self) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        self.documents_widget._on_upload()

    def _on_edit_clicked(self) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        dialog = StudentFormDialog(self._student_service, student_id=self._current_student_id, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self._on_data_changed()

    def _on_upload_photo(self) -> None:
        try:
            self._write_guard.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return
        if self._current_student_id is None:
            return
        from centermanager.ui.student_workspace.profile_image_dialog import ProfileImageDialog
        student = self._student_service.get_student(self._current_student_id)
        dialog = ProfileImageDialog(
            self._student_service,
            self._current_student_id,
            student.profile_image_path,
            parent=self
        )
        if dialog.exec() == ProfileImageDialog.DialogCode.Accepted:
            self._on_data_changed()

    def _on_data_changed(self) -> None:
        if self._current_student_id is not None:
            try:
                self.refresh_current_student()
            except Exception:
                logger.exception("Error refreshing student detail")
            self.student_updated.emit()

    def _export_pdf(self) -> None:
        if not self._collaboration_manager.ensure_write():
            QMessageBox.warning(self, "Read mode", "Start Editing before generating a report.")
            return
        if self._current_student_id is None:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn học sinh.")
            return

        try:
            output_path = self._report_service.generate_student_report(
                self._current_student_id,
                report_type="manual"
            )
            QMessageBox.information(
                self,
                "Xuất thành công",
                f"Báo cáo đã được lưu tại:\n{output_path}"
            )
            self.report_list_widget.set_student(self._current_student_id)
            import os
            import sys
            if sys.platform == 'win32':
                os.startfile(str(output_path.parent))
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.run(['open', str(output_path.parent)])
            else:
                import subprocess
                subprocess.run(['xdg-open', str(output_path.parent)])
        except Exception as e:
            logger.exception("Failed to generate PDF report")
            QMessageBox.critical(self, "Lỗi xuất", f"Không thể tạo báo cáo PDF: {str(e)}")

    def _on_open_finance(self) -> None:
        self.go_to_finance.emit()

    def set_write_enabled(self, enabled: bool) -> None:
        """Propagate write mode to all child mutation surfaces."""
        self._write_enabled = enabled
        for widget in (
            self.quick_actions,
            self.enrollment_widget,
            self.assessment_section,
            self.notes_widget,
            self.documents_widget,
            self.attendance_widget,
            self.report_list_widget,
        ):
            if hasattr(widget, "set_write_enabled"):
                widget.set_write_enabled(enabled)
        for button in self._parent_mutation_buttons:
            button.setEnabled(enabled)
