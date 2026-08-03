# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from centermanager.models.expense import Expense
from centermanager.repositories.base import BaseRepository


class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self, session: Session):
        super().__init__(session, Expense)

    def add(self, expense: Expense) -> Expense:
        self._session.add(expense)
        return expense

    def get_by_id(self, expense_id: int) -> Optional[Expense]:
        return self._session.query(Expense).filter(
            Expense.id == expense_id,
            Expense.deleted_at.is_(None)
        ).first()

    def get_by_id_including_deleted(self, expense_id: int) -> Optional[Expense]:
        return self._session.query(Expense).filter(Expense.id == expense_id).first()

    def list_active(
        self,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Expense]:
        query = self._session.query(Expense).filter(Expense.deleted_at.is_(None))

        if category:
            query = query.filter(Expense.category == category)
        if payment_method:
            query = query.filter(Expense.payment_method == payment_method)
        if status:
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
        query = query.order_by(desc(Expense.payment_date), desc(Expense.created_at))
        return query.offset(offset).limit(limit).all()

    def count_active(
        self,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search_text: Optional[str] = None,
    ) -> int:
        query = self._session.query(Expense).filter(Expense.deleted_at.is_(None))
        if category:
            query = query.filter(Expense.category == category)
        if payment_method:
            query = query.filter(Expense.payment_method == payment_method)
        if status:
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
        return query.count()

    def soft_delete(self, expense: Expense) -> None:
        expense.deleted_at = datetime.now()