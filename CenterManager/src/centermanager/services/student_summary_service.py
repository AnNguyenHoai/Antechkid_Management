# -*- coding: utf-8 -*-
"""
StudentSummaryService - builds summary DTO for a student.
"""
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from centermanager.dto.student_summary_dto import StudentSummaryDTO
from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.exceptions import StudentNotFoundError


class StudentSummaryService:
    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        assessment_service: AssessmentService,
        timeline_service: TimelineService,
    ) -> None:
        self._student_service = student_service
        self._parent_service = parent_service
        self._assessment_service = assessment_service
        self._timeline_service = timeline_service

    def get_summary(self, student_id: int) -> StudentSummaryDTO:
        """Build summary DTO for a student."""
        try:
            student = self._student_service.get_student(student_id)
        except StudentNotFoundError:
            return StudentSummaryDTO()

        # Basic info
        dto = StudentSummaryDTO()
        dto.student_name = student.full_name
        dto.current_level = student.current_level or ""
        dto.learning_status = student.status or ""

        # Age
        if student.date_of_birth:
            today = datetime.now().date()
            age = today.year - student.date_of_birth.year
            if (today.month, today.day) < (student.date_of_birth.month, student.date_of_birth.day):
                age -= 1
            dto.age = age

        # Parents
        parents = self._parent_service.get_parents_for_student(student_id)
        dto.parent_count = len(parents)
        # Primary contact
        primary = next((p for p in parents if p.is_primary_contact), None)
        if primary:
            dto.primary_contact_name = primary.name or ""
            dto.primary_contact_phone = primary.phone or ""
        elif parents:
            dto.primary_contact_name = parents[0].name or ""
            dto.primary_contact_phone = parents[0].phone or ""

        # Assessments
        assessments = self._assessment_service.get_assessments_for_student(student_id)
        dto.assessment_count = len(assessments)
        latest = self._assessment_service.get_latest_assessment(student_id)
        if latest:
            dto.latest_assessment_title = latest.assessment_type or ""
            dto.latest_assessment_score = latest.overall_score
            dto.latest_assessment_date = latest.assessment_date.strftime("%d/%m/%Y") if latest.assessment_date else ""

        # Timeline
        events = self._timeline_service.get_student_timeline(student_id)
        dto.timeline_count = len(events)
        if events:
            latest_event = events[0]
            dto.last_activity_title = latest_event.title
            # Format time
            dt = latest_event.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)  # sử dụng timezone đã import
            dt_local = dt.astimezone()
            now = datetime.now().astimezone()
            if dt_local.date() == now.date():
                time_str = f"Today {dt_local.strftime('%H:%M')}"
            elif (now - dt_local).days == 1:
                time_str = f"Yesterday {dt_local.strftime('%H:%M')}"
            else:
                time_str = dt_local.strftime("%d/%m/%Y %H:%M")
            dto.last_activity_time = time_str

        return dto