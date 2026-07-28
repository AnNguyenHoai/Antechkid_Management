# -*- coding: utf-8 -*-
"""Student UI components."""
from .navigation_panel import NavigationPanel
from .student_workspace import StudentWorkspace
from .student_form_dialog import StudentFormDialog
# Keep old for reference (optional)
from .student_list_page import StudentListPage
from .student_profile_dialog import StudentProfileDialog

__all__ = [
    "NavigationPanel",
    "StudentWorkspace",
    "StudentFormDialog",
    "StudentListPage",
    "StudentProfileDialog",
]