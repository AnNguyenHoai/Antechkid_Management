# -*- coding: utf-8 -*-
"""
StudentSummaryDTO - data transfer object for student summary.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StudentSummaryDTO:
    student_name: str = ""
    current_level: str = ""
    learning_status: str = ""
    age: Optional[int] = None

    latest_assessment_title: str = ""
    latest_assessment_score: Optional[int] = None
    latest_assessment_date: str = ""

    primary_contact_name: str = ""
    primary_contact_phone: str = ""

    last_activity_title: str = ""
    last_activity_time: str = ""

    assessment_count: int = 0
    timeline_count: int = 0
    parent_count: int = 0
    document_count: int = 0   # NEW