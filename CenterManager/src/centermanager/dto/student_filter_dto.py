# -*- coding: utf-8 -*-
"""
StudentFilter DTO for advanced filtering.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StudentFilter:
    """Filter criteria for student list."""
    status: Optional[str] = None          # ACTIVE, ARCHIVED
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    enrollment_status: Optional[str] = None  # enrolled, not_enrolled
    assessment_status: Optional[str] = None  # has_assessment, no_assessment
    class_name: Optional[str] = None