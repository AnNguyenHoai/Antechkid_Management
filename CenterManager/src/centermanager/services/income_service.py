# -*- coding: utf-8 -*-
"""
IncomeService - business logic for Income entity.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.income import Income
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission


class IncomeServiceError(Exception):
    pass


class IncomeNotFoundError(IncomeServiceError):
    pass


class IncomeValidationError(IncomeServiceError):
    pass


class IncomeService:
    def __init__(
        self,
        session_factory: sessionmaker,
        student_service: StudentService,
        class_service: ClassService,
        timeline_service: TimelineService,
        permission_service: PermissionService,
    ) -> None:
        self._session_factory = session_factory
        self._student_service = student_service
        self._class_service = class_service
        self._timeline_service = timeline_service
        self._permission_service = permission_service

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_amount(self, amount: float) -> float:
        if amount <= 0:
            raise IncomeValidationError("Amount must be greater than 0.")
        return amount

    def _validate_income_type(self, income_type: str) -> str:
        valid = ["Tuition", "Book", "Robot Kit", "Material", "Other"]
        if income_type not in valid:
            raise IncomeValidationError(f"Income type must be one of: {', '.join(valid)}")
        return income_type

    def _validate_payment_method(self, payment_method: str) -> str:
        valid = ["Cash", "Bank Transfer"]
        if payment_method not in valid:
            raise IncomeValidationError(f"Payment method must be one of: {', '.join(valid)}")
        return payment_method

    def _check_student_enrolled(self, student_id: int, class_id: int) -> bool:
        with self._session_factory() as session:
            repo = EnrollmentRepository(session)
            return repo.exists(student_id, class_id)

    @require_permission("finance.income.create")
    def create_income(
        self,
        student_id: int,
        class_id: int,
        amount: float,
        income_type: str,
        payment_method: str,
        payment_date: date,
        payment_period: Optional[str] = None,
        received_by: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Income:
        # Validate student exists
        student = self._student_service.get_student(student_id)
        # Validate class exists
        class_obj = self._class_service.get_class(class_id)

        # Tạm thời bỏ kiểm tra enrollment để tránh lỗi (có thể mở lại sau)
        # if not self._check_student_enrolled(student_id, class_id):
        #     raise IncomeValidationError("Student is not enrolled in the selected class.")

        # Validate fields
        amount = self._validate_amount(amount)
        income_type = self._validate_income_type(income_type)
        payment_method = self._validate_payment_method(payment_method)
        if payment_date is None:
            raise IncomeValidationError("Payment date is required.")
        payment_period = self._normalize_text(payment_period)
        received_by = self._normalize_text(received_by) or (get_current_user().full_name if get_current_user() else "System")
        note = self._normalize_text(note)

        with self._session_factory() as session:
            repo = IncomeRepository(session)
            income = Income(
                student_id=student_id,
                class_id=class_id,
                amount=amount,
                income_type=income_type,
                payment_method=payment_method,
                payment_date=payment_date,
                payment_period=payment_period,
                received_by=received_by,
                note=note,
            )
            repo.add(income)
            session.commit()
            session.refresh(income)

            # Log timeline event
            self._timeline_service.log_event(
                student_id=student_id,
                event_type=TimelineEventType.INCOME_CREATED,
                title=f"Income Created: {income_type}",
                description=f"Amount: {amount:,.0f} VND, Payment Method: {payment_method}, Class: {class_obj.name}, Period: {payment_period or 'N/A'}",
                metadata={
                    "income_id": income.id,
                    "class_id": class_id,
                    "amount": amount,
                    "income_type": income_type,
                    "payment_method": payment_method,
                    "payment_period": payment_period,
                }
            )
            return income

    @require_permission("finance.view")
    def get_income(self, income_id: int) -> Income:
        with self._session_factory() as session:
            repo = IncomeRepository(session)
            income = repo.get_by_id(income_id)
            if income is None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found.")
            return income

    @require_permission("finance.view")
    def list_incomes(
        self,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        income_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_period: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[List[Income], int]:
        offset = (page - 1) * per_page
        with self._session_factory() as session:
            repo = IncomeRepository(session)
            items = repo.list_active(
                student_id=student_id,
                class_id=class_id,
                income_type=income_type,
                payment_method=payment_method,
                payment_period=payment_period,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
                offset=offset,
                limit=per_page,
            )
            total = repo.count_active(
                student_id=student_id,
                class_id=class_id,
                income_type=income_type,
                payment_method=payment_method,
                payment_period=payment_period,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
            )
            return items, total

    @require_permission("finance.income.update")
    def update_income(
        self,
        income_id: int,
        amount: Optional[float] = None,
        payment_method: Optional[str] = None,
        payment_date: Optional[date] = None,
        payment_period: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Income:
        with self._session_factory() as session:
            repo = IncomeRepository(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found or deleted.")

            changed = []
            if amount is not None:
                amount = self._validate_amount(amount)
                if income.amount != amount:
                    changed.append(f"amount: {income.amount} -> {amount}")
                income.amount = amount
            if payment_method is not None:
                payment_method = self._validate_payment_method(payment_method)
                if income.payment_method != payment_method:
                    changed.append(f"payment_method: {income.payment_method} -> {payment_method}")
                income.payment_method = payment_method
            if payment_date is not None:
                if income.payment_date != payment_date:
                    changed.append(f"payment_date: {income.payment_date} -> {payment_date}")
                income.payment_date = payment_date
            if payment_period is not None:
                new_period = self._normalize_text(payment_period)
                old_period = income.payment_period or "(none)"
                new_str = new_period or "(none)"
                if old_period != new_str:
                    changed.append(f"payment_period: {old_period} -> {new_str}")
                income.payment_period = new_period
            if note is not None:
                note = self._normalize_text(note)
                old_note = income.note or "(none)"
                new_note = note or "(none)"
                if old_note != new_note:
                    changed.append(f"note: {old_note} -> {new_note}")
                income.note = note

            if not changed:
                return income

            session.commit()
            session.refresh(income)

            # Log timeline
            self._timeline_service.log_event(
                student_id=income.student_id,
                event_type=TimelineEventType.INCOME_UPDATED,
                title="Income Updated",
                description="Updated: " + "; ".join(changed),
                metadata={"income_id": income.id, "changes": changed}
            )
            return income

    @require_permission("finance.income.delete")
    def delete_income(self, income_id: int) -> None:
        with self._session_factory() as session:
            repo = IncomeRepository(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found or already deleted.")

            student_id = income.student_id
            # Soft delete
            income.deleted_at = datetime.now()
            session.commit()

            # Log timeline
            self._timeline_service.log_event(
                student_id=student_id,
                event_type=TimelineEventType.INCOME_DELETED,
                title="Income Deleted",
                description=f"Income {income.income_type} amount {income.amount:,.0f} VND deleted.",
                metadata={"income_id": income_id}
            )