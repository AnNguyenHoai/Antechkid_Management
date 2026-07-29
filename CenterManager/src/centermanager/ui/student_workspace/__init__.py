# -*- coding: utf-8 -*-
"""Student Workspace package."""
from .student_workspace_shell import StudentWorkspaceShell
from .student_dashboard_page import StudentDashboardPage
from .student_list_page import StudentListPage
from .student_detail_page import StudentDetailPage
from .assessment_page import AssessmentPage
from .timeline_page import TimelinePage
from .reports_page import ReportsPage

__all__ = [
    "StudentWorkspaceShell",
    "StudentDashboardPage",
    "StudentListPage",
    "StudentDetailPage",
    "AssessmentPage",
    "TimelinePage",
    "ReportsPage",
]