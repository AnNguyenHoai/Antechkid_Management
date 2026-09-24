# -*- coding: utf-8 -*-
"""Income repository - data access for Income entity."""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from centermanager.core.wallet import WalletMappingError, wallet_aliases
from centermanager.models.class_ import Class
from centermanager.models.income import Income
from centermanager.models.student import Student
from centermanager.repositories.base import BaseRepository


class IncomeRepository(BaseRepository[Income]):
    _SORT_COLUMNS = {
        "payment_date": Income.payment_date,
        "amount": Income.amount,
        "income_type": Income.income_type,
        "payment_method": Income.payment_method,
        "payment_period": Income.payment_period,
        "received_by": Income.received_by,
        "created_at": Income.created_at,
    }

    def __init__(self, session: Session) -> None:
        super().__init__(session, Income)

    def add(self, income: Income) -> Income:
        self._session.add(income)
        return income

    def refresh(self, income: Income) -> Income:
        self._session.refresh(income)
        return income

    def get_by_id(self, income_id: int) -> Optional[Income]:
        """Return any non-deleted transaction, including VOIDED records."""
        return (
            self._session.query(Income)
            .options(joinedload(Income.student), joinedload(Income.class_))
            .filter(Income.id == income_id, Income.deleted_at.is_(None))
            .first()
        )

    def get_by_id_including_deleted(self, income_id: int) -> Optional[Income]:
        return (
            self._session.query(Income)
            .options(joinedload(Income.student), joinedload(Income.class_))
            .filter(Income.id == income_id)
            .first()
        )

    @staticmethod
    def _payment_method_values(payment_method: str):
        try:
            return wallet_aliases(payment_method)
        except WalletMappingError:
            # Raw filtering remains available for migration/diagnostic views of
            # unknown historical values; accounting never guesses their Wallet.
            return (payment_method,)

    def _apply_search(self, query, search_text: str):
        search = f"%{search_text}%"
        return (
            query.outerjoin(Income.student)
            .outerjoin(Income.class_)
            .filter(
                or_(
                    Income.note.ilike(search),
                    Income.payment_period.ilike(search),
                    Income.income_type.ilike(search),
                    Income.payment_method.ilike(search),
                    Income.received_by.ilike(search),
                    Income.status.ilike(search),
                    Student.full_name.ilike(search),
                    Student.student_code.ilike(search),
                    Class.name.ilike(search),
                )
            )
        )

    def _apply_filters(
        self,
        query,
        *,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        income_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_period: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        finance_period_start: Optional[date] = None,
        status: Optional[str] = Income.STATUS_ACTIVE,
    ):
        query = query.filter(Income.deleted_at.is_(None))

        if status:
            query = query.filter(Income.status == status)
        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        if income_type:
            query = query.filter(Income.income_type == income_type)
        if payment_method:
            query = query.filter(
                Income.payment_method.in_(self._payment_method_values(payment_method))
            )
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
        return query

    def list_records(
        self,
        *,
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
        status: Optional[str] = Income.STATUS_ACTIVE,
        sort_by: str = "payment_date",
        ascending: bool = False,
    ) -> List[Income]:
        query = self._session.query(Income).options(
            joinedload(Income.student),
            joinedload(Income.class_),
        )
        query = self._apply_filters(
            query,
            student_id=student_id,
            class_id=class_id,
            income_type=income_type,
            payment_method=payment_method,
            payment_period=payment_period,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            finance_period_start=finance_period_start,
            status=status,
        )

        sort_column = self._SORT_COLUMNS.get(sort_by, Income.payment_date)
        primary_order = asc(sort_column) if ascending else desc(sort_column)
        query = query.order_by(primary_order, desc(Income.created_at), desc(Income.id))
        return query.offset(max(0, offset)).limit(max(1, limit)).all()

    def count_records(
        self,
        *,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        income_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_period: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        finance_period_start: Optional[date] = None,
        status: Optional[str] = Income.STATUS_ACTIVE,
    ) -> int:
        query = self._session.query(Income)
        query = self._apply_filters(
            query,
            student_id=student_id,
            class_id=class_id,
            income_type=income_type,
            payment_method=payment_method,
            payment_period=payment_period,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            finance_period_start=finance_period_start,
            status=status,
        )
        return query.count()

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
        sort_by: str = "payment_date",
        ascending: bool = False,
    ) -> List[Income]:
        """Compatibility API used by live Finance calculations.

        ACTIVE means both not deleted and not voided.
        """
        return self.list_records(
            student_id=student_id,
            class_id=class_id,
            income_type=income_type,
            payment_method=payment_method,
            payment_period=payment_period,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            offset=offset,
            limit=limit,
            finance_period_start=finance_period_start,
            status=Income.STATUS_ACTIVE,
            sort_by=sort_by,
            ascending=ascending,
        )

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
        return self.count_records(
            student_id=student_id,
            class_id=class_id,
            income_type=income_type,
            payment_method=payment_method,
            payment_period=payment_period,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            finance_period_start=finance_period_start,
            status=Income.STATUS_ACTIVE,
        )

    def aggregate_active_tuition_by_student_class(
        self,
        *,
        finance_period_start: date,
        date_from: date,
        date_to: date,
        income_type: str = "Tuition",
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
    ):
        """Return complete ACTIVE tuition totals grouped by student/class in SQL."""
        query = (
            self._session.query(
                Income.student_id,
                Income.class_id,
                func.coalesce(func.sum(Income.amount), 0),
            )
            .filter(
                Income.deleted_at.is_(None),
                Income.status == Income.STATUS_ACTIVE,
                Income.income_type == income_type,
                Income.finance_period_start == finance_period_start,
                Income.payment_date >= date_from,
                Income.payment_date <= date_to,
                Income.student_id.isnot(None),
                Income.class_id.isnot(None),
            )
        )
        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        return query.group_by(Income.student_id, Income.class_id).all()

    def aggregate_active_amounts_by_payment_method(
        self,
        *,
        finance_period_start: date,
        date_from: date,
        date_to: date,
    ):
        """Return complete ACTIVE Income totals grouped by payment method in SQL."""
        return (
            self._session.query(
                Income.payment_method,
                func.coalesce(func.sum(Income.amount), 0),
            )
            .filter(
                Income.deleted_at.is_(None),
                Income.status == Income.STATUS_ACTIVE,
                Income.finance_period_start == finance_period_start,
                Income.payment_date >= date_from,
                Income.payment_date <= date_to,
            )
            .group_by(Income.payment_method)
            .all()
        )

    def delete(self, income: Income) -> None:
        income.deleted_at = datetime.now()
