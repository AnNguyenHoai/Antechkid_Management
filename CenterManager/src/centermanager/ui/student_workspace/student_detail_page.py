# -*- coding: utf-8 -*-
"""Student detail workspace migrated to Design System V2.

The page remains a composition root for Student services and child domain widgets;
UI-PROD-08 changes presentation/state/feedback contracts, not business ownership.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFrame, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from centermanager.models.student import Student
from centermanager.platform.business import WriteGuard
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.context import PlatformContext
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.class_service import ClassService
from centermanager.services.enrollment_service import EnrollmentService
from centermanager.services.exceptions import StudentNotFoundError
from centermanager.services.income_service import IncomeService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.parent_service import ParentService
from centermanager.services.permission_service import PermissionService
from centermanager.services.report_service import ReportService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.session_service import SessionService
from centermanager.services.student_document_service import StudentDocumentService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_note_service import StudentNoteService
from centermanager.services.student_service import StudentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.timeline_service import TimelineService
from centermanager.ui.assessment import AssessmentSection
from centermanager.ui.design_system.feedback import ConfirmationDialog, FeedbackController
from centermanager.ui.design_system.form_detail import DetailSection, EditStateBanner
from centermanager.ui.design_system.foundation import Button, ButtonVariant, EmptyState, ErrorState, Tabs, Toolbar
from centermanager.ui.design_system.tokens import SPACING
from centermanager.ui.parents import ParentCard, ParentDialog
from centermanager.ui.student_workspace.documents_widget import DocumentsWidget
from centermanager.ui.student_workspace.enrollment_widget import EnrollmentWidget
from centermanager.ui.student_workspace.notes_widget import NotesWidget
from centermanager.ui.student_workspace.profile_widget import ProfileWidget
from centermanager.ui.student_workspace.quick_actions_widget import QuickActionsWidget
from centermanager.ui.student_workspace.report_list_widget import ReportListWidget
from centermanager.ui.student_workspace.student_attendance_widget import StudentAttendanceWidget
from centermanager.ui.student_workspace.student_financial_widget import StudentFinancialWidget
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.summary import SummaryWidget
from centermanager.ui.timeline import TimelineWidget

logger = logging.getLogger(__name__)


class StudentDetailPage(QWidget):
    """Student detail with canonical tabs, states, edit projection and feedback."""

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
        parent: Optional[QWidget] = None,
        feedback_controller: Optional[FeedbackController] = None,
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
        self._feedback = feedback_controller or FeedbackController(self)

        self._current_student_id: Optional[int] = None
        self._current_student: Optional[Student] = None
        self._write_enabled = False
        self._parent_mutation_buttons = []
        self._error_state: Optional[ErrorState] = None

        self._setup_ui()
        self._show_empty()

    def set_feedback_controller(self, controller: FeedbackController) -> None:
        self._feedback = controller
        for widget in (self.enrollment_widget, self.financial_tab, self.attendance_widget):
            if hasattr(widget, "set_feedback_controller"):
                widget.set_feedback_controller(controller)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = Toolbar(self)
        self.back_btn = toolbar.add_action(
            "Back to students",
            self.back_clicked.emit,
            variant=ButtonVariant.GHOST,
            align="start",
        )
        main_layout.addWidget(toolbar)

        self.edit_state_banner = EditStateBanner("readonly", parent=self)
        main_layout.addWidget(self.edit_state_banner)

        self.content_state_stack = QStackedWidget(self)
        self.empty_state = EmptyState(
            icon="S",
            title="Select a student",
            description="Choose a student from the list to view profile, enrollment, attendance, and finance context.",
            parent=self.content_state_stack,
        )
        self.content_state_stack.addWidget(self.empty_state)

        self.tab_widget = Tabs(self.content_state_stack)
        self.profile_tab = self._create_profile_tab()
        self.tab_widget.add_page(self.profile_tab, "Profile")

        self.enrollment_widget = EnrollmentWidget(
            self._enrollment_service,
            self._class_service,
            self._collaboration_manager,
            parent=self,
            feedback_controller=self._feedback,
        )
        self.enrollment_widget.enrollment_changed.connect(self._on_data_changed)
        self.tab_widget.add_page(self.enrollment_widget, "Enrollment")

        self.financial_tab = StudentFinancialWidget(
            self._income_service,
            self._student_service,
            self._class_service,
            self._permission_service,
            self._outstanding_service,
            parent=self,
            feedback_controller=self._feedback,
        )
        self.financial_tab.open_finance_clicked.connect(self._on_open_finance)
        self.financial_tab.financial_updated.connect(self._on_data_changed)
        self._finance_tab_index = self.tab_widget.add_page(self.financial_tab, "Finance")

        self.attendance_widget = StudentAttendanceWidget(
            self._attendance_service,
            parent=self,
            feedback_controller=self._feedback,
        )
        self.tab_widget.add_page(self.attendance_widget, "Attendance")

        self.report_list_widget = ReportListWidget(self._report_service, parent=self)
        self.report_list_widget.report_changed.connect(self._on_data_changed)
        self.tab_widget.add_page(self.report_list_widget, "Reports")

        self.content_state_stack.addWidget(self.tab_widget)
        main_layout.addWidget(self.content_state_stack, 1)

    def _create_profile_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        container_layout.setSpacing(SPACING["xl"])

        self.quick_actions = QuickActionsWidget()
        self.quick_actions.upload_photo_clicked.connect(self._on_upload_photo)
        container_layout.addWidget(self.quick_actions)

        self.profile_widget = ProfileWidget()
        container_layout.addWidget(self.profile_widget)

        self.summary_widget = SummaryWidget()
        container_layout.addWidget(self.summary_widget)

        self.parents_section = DetailSection(
            "Parents and guardians",
            "Contacts linked to this student profile.",
            parent=container,
        )
        self.parents_container = QWidget()
        self.parents_layout = QVBoxLayout(self.parents_container)
        self.parents_layout.setContentsMargins(0, 0, 0, 0)
        self.parents_layout.setSpacing(SPACING["sm"])
        self.parents_section.add_widget(self.parents_container)
        container_layout.addWidget(self.parents_section)

        self.assessment_section = AssessmentSection(self._assessment_service)
        self.assessment_section.assessment_changed.connect(self._on_data_changed)
        container_layout.addWidget(self.assessment_section)

        self.timeline_section = DetailSection(
            "Timeline",
            "Recent Student events and lifecycle changes.",
            parent=container,
        )
        self.timeline_widget = TimelineWidget()
        self.timeline_section.add_widget(self.timeline_widget)
        container_layout.addWidget(self.timeline_section)

        self.notes_section = DetailSection("Notes", "Operational notes for this student.", parent=container)
        self.notes_widget = NotesWidget(self._student_note_service)
        self.notes_widget.note_changed.connect(self._on_data_changed)
        self.notes_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.notes_section.add_widget(self.notes_widget)
        container_layout.addWidget(self.notes_section)

        self.documents_section = DetailSection(
            "Documents",
            "Files and artifacts linked to this student.",
            parent=container,
        )
        self.documents_widget = DocumentsWidget(self._document_service)
        self.documents_widget.document_changed.connect(self._on_data_changed)
        self.documents_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.documents_section.add_widget(self.documents_widget)
        container_layout.addWidget(self.documents_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

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

    def _show_empty(self) -> None:
        self._current_student_id = None
        self._current_student = None
        self.content_state_stack.setCurrentWidget(self.empty_state)

    def _show_detail(self) -> None:
        self.content_state_stack.setCurrentWidget(self.tab_widget)

    def _show_error(self, title: str, message: str, *, retry: bool = True) -> None:
        if self._error_state is not None:
            self.content_state_stack.removeWidget(self._error_state)
            self._error_state.deleteLater()
        retry_callback = self.refresh_current_student if retry and self._current_student_id is not None else self.back_clicked.emit
        self._error_state = ErrorState(
            title=title,
            description=message,
            retry_callback=retry_callback,
            parent=self.content_state_stack,
        )
        self.content_state_stack.addWidget(self._error_state)
        self.content_state_stack.setCurrentWidget(self._error_state)

    def refresh_current_student(self) -> None:
        if self._current_student_id is not None:
            self.load_student(self._current_student_id)

    def load_student(self, student_id: int) -> None:
        self._current_student_id = student_id
        try:
            student = self._student_service.get_student(student_id)
        except StudentNotFoundError:
            logger.warning("Student %s not found", student_id)
            self._current_student = None
            self._show_error("Student not found", "This student is no longer available.", retry=False)
            return
        except Exception as exc:
            logger.exception("Error loading student %s", student_id)
            self._current_student = None
            self._show_error("Unable to load student", "The student profile could not be loaded. Try again.")
            self._feedback.system_error(exc, message="The student profile could not be loaded.", retry_action_id="student-detail-refresh", key="student-detail-load")
            return

        self._current_student_id = student.id
        self._current_student = student
        try:
            self._populate_profile(student)
            self.enrollment_widget.set_student(student.id)
            self._populate_financial(student.id)
            self._populate_attendance(student.id)
            self.report_list_widget.set_student(student.id)
        except Exception as exc:
            logger.exception("Error populating student %s", student_id)
            self._show_error("Unable to load student details", "Some student information could not be loaded. Try again.")
            self._feedback.system_error(exc, message="Some student information could not be loaded.", retry_action_id="student-detail-refresh", key="student-detail-load")
            return
        self._show_detail()
        self.set_write_enabled(self._write_enabled)

    def _populate_profile(self, student: Student) -> None:
        parents = self._parent_service.get_parents_for_student(student.id)
        primary = next((parent for parent in parents if parent.is_primary_contact), parents[0] if parents else None)
        self.profile_widget.set_student(
            student,
            primary.name if primary else "",
            primary.phone if primary else "",
        )
        self.summary_widget.set_summary(self._summary_service.get_summary(student.id))
        self._load_parents(student.id)
        self.assessment_section.set_student(student.id)
        self.timeline_widget.set_events(self._timeline_service.get_student_timeline(student.id))
        self.notes_widget.set_student(student.id)
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
        except Exception as exc:
            logger.exception("Error loading parents")
            parents = []
            self._feedback.system_error(exc, message="Parent information could not be loaded.", key="student-parents")

        if not parents:
            empty = EmptyState(
                icon="P",
                title="No parent information",
                description="Add a parent or guardian when contact information is available.",
                action_text="Add parent" if self._write_enabled else None,
                action_callback=self._on_add_parent if self._write_enabled else None,
                parent=self.parents_container,
            )
            self.parents_layout.addWidget(empty)
            return

        for parent in parents:
            card = ParentCard(parent)
            card.edit_clicked.connect(self._on_edit_parent)
            card.delete_clicked.connect(self._on_delete_parent)
            if hasattr(card, "set_write_enabled"):
                card.set_write_enabled(self._write_enabled)
            self.parents_layout.addWidget(card)

        add_btn = Button("Add parent", variant=ButtonVariant.SECONDARY, parent=self.parents_container)
        add_btn.clicked.connect(self._on_add_parent)
        add_btn.setEnabled(self._write_enabled)
        self._parent_mutation_buttons.append(add_btn)
        self.parents_layout.addWidget(add_btn)

    def _clear_parents(self) -> None:
        self._parent_mutation_buttons = []
        while self.parents_layout.count():
            item = self.parents_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _require_write(self, action: str) -> bool:
        try:
            self._write_guard.require_write()
            return True
        except Exception:
            self._feedback.warning(
                f"Start editing before you {action} this student.",
                title="Read-only mode",
                key="student-write-required",
            )
            return False

    def _on_add_parent(self) -> None:
        if not self._require_write("change") or self._current_student_id is None:
            return
        dialog = ParentDialog(self._parent_service, self._current_student_id, parent_widget=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_data_changed()
            self._feedback.success("Parent saved", key="student-parent")

    def _on_edit_parent(self, parent_id: int) -> None:
        if not self._require_write("change") or self._current_student_id is None:
            return
        dialog = ParentDialog(
            self._parent_service,
            self._current_student_id,
            parent_id=parent_id,
            parent_widget=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_data_changed()
            self._feedback.success("Parent saved", key="student-parent")

    def _on_delete_parent(self, parent_id: int) -> None:
        if not self._require_write("change"):
            return
        confirm = ConfirmationDialog(
            "Delete parent",
            "Delete this parent or guardian from the student profile?",
            confirm_text="Delete parent",
            dangerous=True,
            parent=self,
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._parent_service.delete_parent(parent_id)
            self._on_data_changed()
            self._feedback.deleted(message="Parent deleted", key="student-parent")
        except Exception as exc:
            logger.exception("Delete parent failed")
            self._feedback.system_error(exc, message="The parent could not be deleted.", key="student-parent")

    def _on_add_assessment(self) -> None:
        if not self._require_write("add an assessment") or self._current_student_id is None:
            return
        from centermanager.ui.assessment.assessment_dialog import AssessmentDialog
        dialog = AssessmentDialog(self._assessment_service, self._current_student_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_data_changed()
            self._feedback.success("Assessment saved", key="student-assessment")

    def _on_add_note(self) -> None:
        if self._require_write("add a note") and self._current_student_id is not None:
            self.notes_widget._on_add()

    def _on_upload_doc(self) -> None:
        if self._require_write("upload a document") and self._current_student_id is not None:
            self.documents_widget._on_upload()

    def _on_edit_clicked(self) -> None:
        if not self._require_write("edit") or self._current_student_id is None:
            return
        dialog = StudentFormDialog(
            self._student_service,
            student_id=self._current_student_id,
            parent=self,
            feedback_controller=self._feedback,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_data_changed()

    def _on_upload_photo(self) -> None:
        if not self._require_write("upload a photo") or self._current_student_id is None:
            return
        from centermanager.ui.student_workspace.profile_image_dialog import ProfileImageDialog
        try:
            student = self._student_service.get_student(self._current_student_id)
            dialog = ProfileImageDialog(
                self._student_service,
                self._current_student_id,
                student.profile_image_path,
                parent=self,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._on_data_changed()
                self._feedback.success("Profile photo updated", key="student-photo")
        except Exception as exc:
            logger.exception("Profile photo flow failed")
            self._feedback.system_error(exc, message="The profile photo could not be updated.", key="student-photo")

    def _on_data_changed(self) -> None:
        if self._current_student_id is not None:
            try:
                self.refresh_current_student()
            except Exception:
                logger.exception("Error refreshing student detail")
            self.student_updated.emit()

    def _export_pdf(self) -> None:
        if self._current_student_id is None:
            self._feedback.info("Select a student before exporting a report.", key="student-report")
            return
        operation_id = f"student-report-{self._current_student_id}"
        if not self._feedback.begin_operation(operation_id, "Generating student report…"):
            return
        try:
            output_path = self._report_service.generate_student_report(
                self._current_student_id,
                report_type="manual",
            )
            self._feedback.finish_operation(operation_id)
            self._feedback.success(f"Student report saved to {output_path}", key="student-report")
            self.report_list_widget.set_student(self._current_student_id)
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            logger.exception("Failed to generate PDF report")
            self._feedback.system_error(exc, message="The student report could not be generated.", key="student-report")

    def _on_open_finance(self) -> None:
        try:
            if not self._permission_service.has_permission("finance.view"):
                self._feedback.warning(
                    "Your current role does not allow access to the Finance Workspace.",
                    title="Finance access required",
                    key="student-finance-permission",
                )
                return
        except Exception as exc:
            logger.exception("Failed to validate finance navigation permission")
            self._feedback.system_error(exc, message="Finance access could not be verified.", key="student-finance-permission")
            return
        self.go_to_finance.emit()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self.edit_state_banner.set_state("editing" if enabled else "readonly")
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
