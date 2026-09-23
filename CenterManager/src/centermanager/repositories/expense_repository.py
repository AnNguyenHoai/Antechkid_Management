# -*- coding: utf-8 -*-
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session

from centermanager.models.expense import Expense
from centermanager.repositories.base import BaseRepository


class ExpenseRepository(BaseRepository[Expense]):
    """Expense persistence with server-side filtering, sorting and paging."""

    # ``Paid`` is retained as a legacy realized state for existing databases/tests.
    REALIZED_STATUSES = ("Completed", "Paid")
    PAYMENT_METHOD_EQUIVALENTS = {
        "Cash": ("Cash", "TÀI KHOẢN CÁ NHÂN"),
        "Bank": ("Bank", "Bank Transfer", "TÀI KHOẢN CÔNG TY"),
        "Other": ("Other",),
    }
    SORT_COLUMNS = {
        "payment_date": Expense.payment_date,
        "category": Expense.category,
        "description": Expense.description,
        "amount": Expense.amount,
        "payment_method": Expense.payment_method,
        "paid_by": Expense.paid_by,
        "status": Expense.status,
        "created_at": Expense.created_at,
    }

    def __init__(self, session: Session):
        super().__init__(session, Expense)

    def add(self, expense: Expense) -> Expense:
        self._session.add(expense)
        return expense

    def get_by_id(self, expense_id: int) -> Optional[Expense]:
        return self._session.query(Expense).filter(
            Expense.id == expense_id,
            Expense.deleted_at.is_(None),
        ).first()

    def get_by_id_including_deleted(self, expense_id: int) -> Optional[Expense]:
        return self._session.query(Expense).filter(Expense.id == expense_id).first()

    def _filtered_query(
        self,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        finance_period_start: Optional[date] = None,
        realized_only: bool = False,
    ):
        query = self._session.query(Expense).filter(Expense.deleted_at.is_(None))
        if finance_period_start:
            query = query.filter(Expense.payment_date >= finance_period_start)
        if category:
            query = query.filter(Expense.category == category)
        if payment_method:
            equivalents = self.PAYMENT_METHOD_EQUIVALENTS.get(
                payment_method, (payment_method,)
            )
            query = query.filter(Expense.payment_method.in_(equivalents))
        if realized_only:
            query = query.filter(Expense.status.in_(self.REALIZED_STATUSES))
        elif status:
            if status == "Completed":
                query = query.filter(Expense.status.in_(self.REALIZED_STATUSES))
            else:
                query = query.filter(Expense.status == status)
        if date_from:
            query = query.filter(Expense.payment_date >= date_from)
        if date_to:
            query = query.filter(Expense.payment_date <= date_to)
        if search_text:
            search = f"%{search_text}%"
            query = query.filter(
                or_(
                    Expense.category.ilike(search),
                    Expense.description.ilike(search),
                    Expense.paid_by.ilike(search),
                    Expense.note.ilike(search),
                )
            )
        return query

    def list_active(
        self,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        finance_period_start: Optional[date] = None,
        sort_by: str = "payment_date",
        ascending: bool = False,
        realized_only: bool = False,
    ) -> List[Expense]:
        query = self._filtered_query(
            category=category,
            payment_method=payment_method,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            finance_period_start=finance_period_start,
            realized_only=realized_only,
        )
        column = self.SORT_COLUMNS.get(sort_by, Expense.payment_date)
        ordering = asc(column) if ascending else desc(column)
        query = query.order_by(ordering, desc(Expense.created_at))
        return query.offset(max(0, offset)).limit(max(1, limit)).all()

    def count_active(
        self,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        finance_period_start: Optional[date] = None,
        realized_only: bool = False,
    ) -> int:
        return self._filtered_query(
            category=category,
            payment_method=payment_method,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            finance_period_start=finance_period_start,
            realized_only=realized_only,
        ).count()

    def soft_delete(self, expense: Expense) -> None:
        expense.deleted_at = datetime.now()
