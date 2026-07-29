# -*- coding: utf-8 -*-
"""
TimelineWorkspace - Shell for Timeline Workspace.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame

from centermanager.services.timeline_service import TimelineService
from centermanager.services.student_service import StudentService
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.timeline.timeline_feed_page import TimelineFeedPage


class TimelineWorkspace(QWidget):
    go_home = Signal()

    def __init__(
        self,
        timeline_service: TimelineService,
        student_service: StudentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._timeline_service = timeline_service
        self._student_service = student_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Timeline Workspace", "Feed")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "feed", "icon": "📅", "label": "Timeline Feed"},
        ]
        self.nav = WorkspaceNavigation("Timeline Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.feed_page = TimelineFeedPage(self._timeline_service, self._student_service)
        self.content_stack.addWidget(self.feed_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

        self.navigate_to("feed")

    def navigate_to(self, page_id: str) -> None:
        self.content_stack.setCurrentIndex(0)
        self.nav.set_active_page(page_id)
        self.header.set_context("Timeline Workspace", "Feed")
        self.feed_page.refresh()