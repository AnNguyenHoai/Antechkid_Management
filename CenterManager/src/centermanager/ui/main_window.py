# -*- coding: utf-8 -*-
"""
Main window – two-column layout.
"""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QSplitter, QPushButton
)
from PySide6.QtCore import Qt

from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.ui.students.navigation_panel import NavigationPanel
from centermanager.ui.students.student_workspace import StudentWorkspace
from centermanager.ui.students.student_form_dialog import StudentFormDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):

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
        self.setWindowTitle("CenterManager")
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #f0f0f0; padding: 2px 12px;")
        toolbar.setFixedHeight(40)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("CenterManager")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        toolbar_layout.addWidget(title)
        toolbar_layout.addStretch()

        self.add_btn = QPushButton("+ Add Student")
        self.add_btn.setFixedHeight(28)
        toolbar_layout.addWidget(self.add_btn)

        main_layout.addWidget(toolbar)

        # Splitter: Navigation | Workspace
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.navigation = NavigationPanel()
        self.workspace = StudentWorkspace(
            student_service=self._student_service,
            parent_service=self._parent_service,
            timeline_service=self._timeline_service,
            assessment_service=self._assessment_service,
            summary_service=self._summary_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
        )

        splitter.addWidget(self.navigation)
        splitter.addWidget(self.workspace)
        splitter.setSizes([280, 620])

        main_layout.addWidget(splitter)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Signals
        self.navigation.student_selected.connect(self._on_student_selected)
        self.workspace.student_updated.connect(self.refresh_navigation)
        self.add_btn.clicked.connect(self._on_add_clicked)

        self.refresh_navigation()

    def _on_student_selected(self, student_id: int) -> None:
        self.workspace.load_student(student_id)

    def _on_add_clicked(self) -> None:
        dialog = StudentFormDialog(self._student_service, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh_navigation()

    def refresh_navigation(self) -> None:
        try:
            students = self._student_service.list_students()
            self.navigation.set_students(students)
            self.statusBar().showMessage(f"Loaded {len(students)} students")
        except Exception as e:
            logger.exception("Failed to refresh student list")
            self.statusBar().showMessage("Unable to load students.")