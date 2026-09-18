# -*- coding: utf-8 -*-
"""
Income repository - data access for Income entity.
"""
from typing import List, Optional
from datetime import date, datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_

from centermanager.models.income import Income
from centermanager.models.student import Student
from centermanager.models.class_ import Class
from centermanager.repositories.base import BaseRepository


class IncomeRepository(BaseRepository[Income]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Income)

    def add(self, income: Income) -> Income:
        self._session.add(income)
        return income

    def refresh(self, income: Income) -> Income:
        self._session.refresh(income)
        return income

    def get_by_id(self, income_id: int) -> Optional[Income]:
        return self._session.query(Income).options(
            joinedload(Income.student),
            joinedload(Income.class_)
        ).filter(Income.id == income_id, Income.deleted_at.is_(None)).first()

    def get_by_id_including_deleted(self, income_id: int) -> Optional[Income]:
        return self._session.query(Income).options(
            joinedload(Income.student),
            joinedload(Income.class_)
        ).filter(Income.id == income_id).first()

    def _apply_search(self, query, search_text: str):
        """Search without excluding income rows whose student/class links are NULL."""
        search = f"%{search_text}%"
        return (
            query.outerjoin(Income.student)
            .outerjoin(Income.class_)
            .filter(
                or_(
                    Income.note.ilike(search),
                    Income.payment_period.ilike(search),
                    Income.income_type.ilike(search),
                    Income.received_by.ilike(search),
                    Student.full_name.ilike(search),
                    Student.student_code.ilike(search),
                    Class.name.ilike(search),
                )
            )
        )

    def list_active(
        self,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        income_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_period: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        finance_period_start: Optional[date] = None,
    ) -> List[Income]:
        query = self._session.query(Income).options(
            joinedload(Income.student),
            joinedload(Income.class_)
        ).filter(Income.deleted_at.is_(None))

        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        if income_type:
            query = query.filter(Income.income_type == income_type)
        if payment_method:
            query = query.filter(Income.payment_method == payment_method)
        if payment_period:
            query = query.filter(Income.payment_period == payment_period)
        if finance_period_start:
            query = query.filter(Income.finance_period_start == finance_period_start)
        if date_from:
            query = query.filter(Income.payment_date >= date_from)
        if date_to:
            query = query.filter(Income.payment_date <= date_to)
        if search_text:
            query = self._apply_search(query, search_text)

        query = query.order_by(desc(Income.payment_date), desc(Income.created_at))
        return query.offset(offset).limit(limit).all()

    def count_active(
        self,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        income_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_period: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        finance_period_start: Optional[date] = None,
    ) -> int:
        query = self._session.query(Income).filter(Income.deleted_at.is_(None))
        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        if income_type:
            query = query.filter(Income.income_type == income_type)
        if payment_method:
            query = query.filter(Income.payment_method == payment_method)
        if payment_period:
            query = query.filter(Income.payment_period == payment_period)
        if finance_period_start:
            query = query.filter(Income.finance_period_start == finance_period_start)
        if date_from:
            query = query.filter(Income.payment_date >= date_from)
        if date_to:
            query = query.filter(Income.payment_date <= date_to)
        if search_text:
            query = self._apply_search(query, search_text)
        return query.count()

    def delete(self, income: Income) -> None:
        income.deleted_at = datetime.now()
