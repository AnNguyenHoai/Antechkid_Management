# -*- coding: utf-8 -*-
"""
AssessmentService - business logic for Assessment entity.
Now with ReportPolicy integration.
"""
from datetime import date
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import sessionmaker

from centermanager.models.assessment import Assessment, AssessmentType
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.assessment_repository import AssessmentRepository
from centermanager.services.timeline_service import TimelineService

if TYPE_CHECKING:
    from centermanager.services.report_policy import ReportPolicy
    from centermanager.services.report_service import ReportService


class AssessmentServiceError(Exception):
    pass


class AssessmentNotFoundError(AssessmentServiceError):
    pass


class AssessmentValidationError(AssessmentServiceError):
    pass


class AssessmentService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: Optional[TimelineService] = None,
        report_policy: Optional["ReportPolicy"] = None,
        report_service: Optional["ReportService"] = None,
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._report_policy = report_policy
        self._report_service = report_service

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_assessment_type(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        valid = [e.value for e in AssessmentType]
        if value not in valid:
            raise AssessmentValidationError(f"Assessment type must be one of: {', '.join(valid)}")
        return value

    def _validate_score(self, score: Optional[int]) -> Optional[int]:
        if score is None:
            return None
        if not isinstance(score, int) or score < 0 or score > 5:
            raise AssessmentValidationError("Score must be between 0 and 5.")
        return score

    def _trigger_report_policy(self, student_id: int, event_type: str, event_data: Optional[dict] = None) -> None:
        """Helper method to trigger report policy if available."""
        if self._report_policy and self._report_service:
            triggers = self._report_policy.check_and_trigger(student_id, event_type, event_data)
            for trigger in triggers:
                try:
                    self._report_service.generate_student_report(
                        student_id,
                        report_type="automatic",
                        trigger_event=trigger,
                        generated_by="system"
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).exception(f"Failed to generate automatic report for student {student_id}, trigger {trigger}: {e}")

    def create_assessment(
        self,
        student_id: int,
        assessment_date: date,
        assessment_type: str,
        strengths: str,
        improvements: str,
        next_goal: str,
        teacher_comment: Optional[str] = None,
        overall_score: Optional[int] = None,
    ) -> Assessment:
        norm_type = self._validate_assessment_type(assessment_type)
        if not norm_type:
            raise AssessmentValidationError("Assessment type is required.")
        if assessment_date is None:
            raise AssessmentValidationError("Assessment date is required.")
        norm_strengths = self._normalize_text(strengths)
        if not norm_strengths:
            raise AssessmentValidationError("Strengths is required.")
        norm_improvements = self._normalize_text(improvements)
        if not norm_improvements:
            raise AssessmentValidationError("Improvements is required.")
        norm_next_goal = self._normalize_text(next_goal)
        if not norm_next_goal:
            raise AssessmentValidationError("Next goal is required.")
        norm_comment = self._normalize_text(teacher_comment)
        norm_score = self._validate_score(overall_score)

        with self._session_factory() as session:
            assessment = Assessment(
                student_id=student_id,
                assessment_date=assessment_date,
                assessment_type=norm_type,
                overall_score=norm_score,
                strengths=norm_strengths,
                improvements=norm_improvements,
                next_goal=norm_next_goal,
                teacher_comment=norm_comment,
            )
            repo = AssessmentRepository(session)
            repo.add(assessment)
            session.commit()
            session.refresh(assessment)

            if self._timeline_service:
                score_str = f" ({norm_score}/5)" if norm_score is not None else ""
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.ASSESSMENT_CREATED,
                    title="Assessment Created",
                    description=f"{norm_type} assessment{score_str} on {assessment_date.strftime('%d/%m/%Y')}",
                    metadata={"assessment_id": assessment.id},
                )

            # Trigger report policy
            self._trigger_report_policy(student_id, "assessment_created", {"assessment_id": assessment.id})

            return assessment

    def get_assessment(self, assessment_id: int) -> Assessment:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            assessment = repo.get_by_id(assessment_id)
            if assessment is None:
                raise AssessmentNotFoundError(f"Assessment id {assessment_id} not found.")
            return assessment

    def get_assessments_for_student(self, student_id: int) -> List[Assessment]:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            return repo.get_by_student(student_id)

    def get_latest_assessment(self, student_id: int) -> Optional[Assessment]:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            return repo.get_latest(student_id)

    def update_assessment(
        self,
        assessment_id: int,
        assessment_date: Optional[date] = None,
        assessment_type: Optional[str] = None,
        overall_score: Optional[int] = None,
        strengths: Optional[str] = None,
        improvements: Optional[str] = None,
        next_goal: Optional[str] = None,
        teacher_comment: Optional[str] = None,
    ) -> Assessment:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            assessment = repo.get_by_id(assessment_id)
            if assessment is None:
                raise AssessmentNotFoundError(f"Assessment id {assessment_id} not found.")

            changes = []

            if assessment_date is not None:
                old = assessment.assessment_date.strftime("%d/%m/%Y") if assessment.assessment_date else "(none)"
                new = assessment_date.strftime("%d/%m/%Y")
                if old != new:
                    changes.append(f"date: '{old}' -> '{new}'")
                assessment.assessment_date = assessment_date

            if assessment_type is not None:
                new_val = self._validate_assessment_type(assessment_type)
                old_val = assessment.assessment_type or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"type: '{old_val}' -> '{new_val or '(none)'}'")
                assessment.assessment_type = new_val

            if overall_score is not None:
                new_val = self._validate_score(overall_score)
                old_val = assessment.overall_score if assessment.overall_score is not None else "(none)"
                new_str = str(new_val) if new_val is not None else "(none)"
                if str(old_val) != new_str:
                    changes.append(f"score: '{old_val}' -> '{new_str}'")
                assessment.overall_score = new_val

            if strengths is not None:
                new_val = self._normalize_text(strengths)
                if not new_val:
                    raise AssessmentValidationError("Strengths cannot be empty.")
                old_val = assessment.strengths or "(none)"
                if old_val != new_val:
                    changes.append(f"strengths: '{old_val}' -> '{new_val}'")
                assessment.strengths = new_val

            if improvements is not None:
                new_val = self._normalize_text(improvements)
                if not new_val:
                    raise AssessmentValidationError("Improvements cannot be empty.")
                old_val = assessment.improvements or "(none)"
                if old_val != new_val:
                    changes.append(f"improvements: '{old_val}' -> '{new_val}'")
                assessment.improvements = new_val

            if next_goal is not None:
                new_val = self._normalize_text(next_goal)
                if not new_val:
                    raise AssessmentValidationError("Next goal cannot be empty.")
                old_val = assessment.next_goal or "(none)"
                if old_val != new_val:
                    changes.append(f"next_goal: '{old_val}' -> '{new_val}'")
                assessment.next_goal = new_val

            if teacher_comment is not None:
                new_val = self._normalize_text(teacher_comment)
                old_val = assessment.teacher_comment or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"comment: '{old_val}' -> '{new_val or '(none)'}'")
                assessment.teacher_comment = new_val

            if not changes:
                return assessment

            session.commit()
            session.refresh(assessment)

            if self._timeline_service:
                description = "Updated: " + "; ".join(changes)
                self._timeline_service.log_event(
                    student_id=assessment.student_id,
                    event_type=TimelineEventType.ASSESSMENT_UPDATED,
                    title="Assessment Updated",
                    description=description,
                    metadata={"assessment_id": assessment.id, "changes": changes},
                )

            # Trigger report policy
            self._trigger_report_policy(assessment.student_id, "assessment_updated", {"assessment_id": assessment.id})

            return assessment

    def delete_assessment(self, assessment_id: int) -> None:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            assessment = repo.get_by_id(assessment_id)
            if assessment is None:
                raise AssessmentNotFoundError(f"Assessment id {assessment_id} not found.")
            student_id = assessment.student_id
            repo.delete(assessment)
            session.commit()

            if self._timeline_service:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.ASSESSMENT_DELETED,
                    title="Assessment Deleted",
                    description=f"Assessment on {assessment.assessment_date.strftime('%d/%m/%Y')} was removed.",
                    metadata={"assessment_id": assessment_id},
                )

            # Không trigger report khi xóa

    def get_all_assessments_with_student(self) -> List[Assessment]:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            return repo.get_all_with_student()

    def get_assessments_for_student_with_student(self, student_id: int) -> List[Assessment]:
        with self._session_factory() as session:
            repo = AssessmentRepository(session)
            return repo.get_by_student_with_student(student_id)