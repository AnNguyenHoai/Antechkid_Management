# -*- coding: utf-8 -*-
import logging
from datetime import date, datetime
from typing import Optional, List, Tuple
from sqlalchemy.orm import sessionmaker

from centermanager.models.expense import Expense
from centermanager.repositories.expense_repository import ExpenseRepository
from centermanager.services.expense_timeline_service import ExpenseTimelineService
from centermanager.services.permission_service import PermissionService
from centermanager.core.permission_guard import require_permission
from centermanager.core.current_user import get_current_user

logger = logging.getLogger(__name__)


class ExpenseValidationError(Exception):
    pass


class ExpenseNotFoundError(Exception):
    pass


class ExpenseService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: ExpenseTimelineService,
        permission_service: PermissionService,
    ):
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._permission_service = permission_service

    def _normalize_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = text.strip()
        return stripped if stripped else None

    def _validate_amount(self, amount: float) -> float:
        if amount <= 0:
            raise ExpenseValidationError("Amount must be greater than 0")
        return amount

    def _validate_category(self, category: str) -> str:
        valid = [
            "Teacher Salary", "Office Rent", "Electricity", "Water",
            "Internet", "Equipment", "Marketing", "Office Supply",
            "Maintenance", "Transportation", "Other"
        ]
        if category not in valid:
            raise ExpenseValidationError(f"Category must be one of: {', '.join(valid)}")
        return category

    def _validate_payment_method(self, method: str) -> str:
        valid = ["","TÀI KHOẢN CÁ NHÂN", "TÀI KHOẢN CÔNG TY"]
        if method not in valid:
            raise ExpenseValidationError(f"Payment method must be one of: {', '.join(valid)}")
        return method

    def _validate_status(self, status: str) -> str:
        valid = ["","ĐÃ HOÀN TRẢ", "CHƯA HOÀN TRẢ"]
        if status not in valid:
            raise ExpenseValidationError(f"Status must be one of: {', '.join(valid)}")
        return status

    @require_permission("finance.expense.create")
    def create_expense(
        self,
        category: str,
        description: str,
        amount: float,
        payment_method: str,
        payment_date: date,
        paid_by: Optional[str] = None,
        status: str = "Completed",
        note: Optional[str] = None,
    ) -> Expense:
        category = self._validate_category(category)
        description = self._normalize_text(description)
        if not description:
            raise ExpenseValidationError("Description is required")
        amount = self._validate_amount(amount)
        payment_method = self._validate_payment_method(payment_method)
        status = self._validate_status(status)
        paid_by = self._normalize_text(paid_by) or (get_current_user().full_name if get_current_user() else "System")
        note = self._normalize_text(note)

        with self._session_factory() as session:
            repo = ExpenseRepository(session)
            expense = Expense(
                category=category,
                description=description,
                amount=amount,
                payment_method=payment_method,
                payment_date=payment_date,
                paid_by=paid_by,
                status=status,
                note=note,
            )
            repo.add(expense)
            session.commit()
            session.refresh(expense)

            self._timeline_service.log_event(
                expense_id=expense.id,
                event_type="ExpenseCreated",
                title=f"Expense Created: {category}",
                description=f"Amount: {amount:,.0f} VND, Method: {payment_method}",
                metadata={"category": category, "amount": amount},
            )
            return expense

    @require_permission("finance.view")
    def get_expense(self, expense_id: int) -> Expense:
        with self._session_factory() as session:
            repo = ExpenseRepository(session)
            expense = repo.get_by_id(expense_id)
            if not expense:
                raise ExpenseNotFoundError(f"Expense {expense_id} not found")
            return expense

    @require_permission("finance.view")
    def list_expenses(
        self,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Expense], int]:
        offset = (page - 1) * per_page
        with self._session_factory() as session:
            repo = ExpenseRepository(session)
            items = repo.list_active(
                category=category,
                payment_method=payment_method,
                status=status,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
                offset=offset,
                limit=per_page,
            )
            total = repo.count_active(
                category=category,
                payment_method=payment_method,
                status=status,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
            )
            return items, total

    @require_permission("finance.expense.update")
    def update_expense(
        self,
        expense_id: int,
        category: Optional[str] = None,
        description: Optional[str] = None,
        amount: Optional[float] = None,
        payment_method: Optional[str] = None,
        payment_date: Optional[date] = None,
        paid_by: Optional[str] = None,
        status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Expense:
        with self._session_factory() as session:
            repo = ExpenseRepository(session)
            expense = repo.get_by_id_including_deleted(expense_id)
            if not expense or expense.deleted_at is not None:
                raise ExpenseNotFoundError(f"Expense {expense_id} not found or deleted")

            changes = []

            if category is not None:
                new_cat = self._validate_category(category)
                if expense.category != new_cat:
                    changes.append(f"category: {expense.category} -> {new_cat}")
                    expense.category = new_cat

            if description is not None:
                new_desc = self._normalize_text(description)
                if not new_desc:
                    raise ExpenseValidationError("Description cannot be empty")
                if expense.description != new_desc:
                    changes.append(f"description: {expense.description} -> {new_desc}")
                    expense.description = new_desc

            if amount is not None:
                new_amount = self._validate_amount(amount)
                if expense.amount != new_amount:
                    changes.append(f"amount: {expense.amount} -> {new_amount}")
                    expense.amount = new_amount

            if payment_method is not None:
                new_method = self._validate_payment_method(payment_method)
                if expense.payment_method != new_method:
                    changes.append(f"payment_method: {expense.payment_method} -> {new_method}")
                    expense.payment_method = new_method

            if payment_date is not None:
                if expense.payment_date != payment_date:
                    changes.append(f"payment_date: {expense.payment_date} -> {payment_date}")
                    expense.payment_date = payment_date

            if paid_by is not None:
                new_paid = self._normalize_text(paid_by) or "System"
                if expense.paid_by != new_paid:
                    changes.append(f"paid_by: {expense.paid_by} -> {new_paid}")
                    expense.paid_by = new_paid

            if status is not None:
                new_status = self._validate_status(status)
                if expense.status != new_status:
                    changes.append(f"status: {expense.status} -> {new_status}")
                    expense.status = new_status

            if note is not None:
                new_note = self._normalize_text(note)
                old_note = expense.note or "(none)"
                new_str = new_note or "(none)"
                if old_note != new_str:
                    changes.append(f"note: {old_note} -> {new_str}")
                    expense.note = new_note

            if not changes:
                return expense

            session.commit()
            session.refresh(expense)

            self._timeline_service.log_event(
                expense_id=expense.id,
                event_type="ExpenseUpdated",
                title="Expense Updated",
                description="; ".join(changes),
                metadata={"changes": changes},
            )
            return expense

    @require_permission("finance.expense.delete")
    def delete_expense(self, expense_id: int) -> None:
        with self._session_factory() as session:
            repo = ExpenseRepository(session)
            expense = repo.get_by_id_including_deleted(expense_id)
            if not expense or expense.deleted_at is not None:
                raise ExpenseNotFoundError(f"Expense {expense_id} not found or already deleted")
            repo.soft_delete(expense)
            session.commit()

            self._timeline_service.log_event(
                expense_id=expense.id,
                event_type="ExpenseDeleted",
                title="Expense Deleted",
                description=f"Expense {expense.category} amount {expense.amount:,.0f} VND deleted",
            )