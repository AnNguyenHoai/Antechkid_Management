# -*- coding: utf-8 -*-
"""Student UI components."""
from .student_form_dialog import StudentFormDialog
from .helpers import calculate_age, format_date_for_display, format_age_for_display

__all__ = [
    "StudentFormDialog",
    "calculate_age",
    "format_date_for_display",
    "format_age_for_display",
]