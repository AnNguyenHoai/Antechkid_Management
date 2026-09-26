# -*- coding: utf-8 -*-
"""Income repository - data access for Income entity."""
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from centermanager.core.wallet import WalletMappingError, wallet_aliases
from centermanager.models.class_ import Class
from centermanager.models.enrollment_transfer import EnrollmentTransfer
from centermanager.models.income import Income
from centermanager.models.student import Student
from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.repositories.base import BaseRepository


@dataclass(frozen=True)
class TuitionSettlementComponent:
    """One signed component contributing to an Enrollment's settled tuition."""

    KIND_PAYMENT = "PAYMENT"
    KIND_REFUND = "REFUND"
    KIND_CREDIT_ADJUSTMENT = "CREDIT_ADJUSTMENT"
    KIND_TRANSFER_IN = "TRANSFER_IN"
    KIND_TRANSFER_OUT = "TRANSFER_OUT"

    SOURCE_INCOME = "INCOME"
    SOURCE_ADJUSTMENT = "TUITION_ADJUSTMENT"
    SOURCE_TRANSFER = "ENROLLMENT_TRANSFER"

    kind: str
    source: str
    source_id: int
    effective_date: date
    amount: Decimal
    wallet: Optional[str] = None
    note: Optional[str] = None
    counterparty_enrollment_id: Optional[int] = None


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
    _SETTLEMENT_KIND_ORDER = {
        TuitionSettlementComponent.KIND_PAYMENT: 0,
        TuitionSettlementComponent.KIND_REFUND: 1,
        TuitionSettlementComponent.KIND_CREDIT_ADJUSTMENT: 2,
        TuitionSettlementComponent.KIND_TRANSFER_IN: 3,
        TuitionSettlementComponent.KIND_TRANSFER_OUT: 4,
    }

    def __init__(self, session: Session) -> None:
        super().__init__(session, Income)

    def add(self, income: Income) -> Income:
        self._session.add(income)
        return income

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, income: Income) -> Income:
        self._session.refresh(income)
        return income

    @staticmethod
    def _load_options():
        return (
            joinedload(Income.student),
            joinedload(Income.class_),
            joinedload(Income.enrollment),
        )

    def get_by_id(self, income_id: int) -> Optional[Income]:
        return self._session.query(Income).options(*self._load_options()).filter(
            Income.id == income_id, Income.deleted_at.is_(None)
        ).first()

    def get_by_id_including_deleted(self, income_id: int) -> Optional[Income]:
        return self._session.query(Income).options(*self._load_options()).filter(Income.id == income_id).first()

    @staticmethod
    def _payment_method_values(payment_method: str):
        try:
            return wallet_aliases(payment_method)
        except WalletMappingError:
            return (payment_method,)

    def _apply_search(self, query, search_text: str):
        search = f"%{search_text}%"
        return query.outerjoin(Income.student).outerjoin(Income.class_).filter(
            or_(
                Income.note.ilike(search), Income.payment_period.ilike(search),
                Income.income_type.ilike(search), Income.payment_method.ilike(search),
                Income.received_by.ilike(search), Income.status.ilike(search),
                Student.full_name.ilike(search), Student.student_code.ilike(search), Class.name.ilike(search),
            )
        )

    def _apply_filters(self, query, *, student_id=None, class_id=None, enrollment_id=None,
                       income_type=None, payment_method=None, payment_period=None, date_from=None,
                       date_to=None, search_text=None, finance_period_start=None,
                       status: Optional[str] = Income.STATUS_ACTIVE):
        query = query.filter(Income.deleted_at.is_(None))
        if status:
            query = query.filter(Income.status == status)
        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        if enrollment_id is not None:
            query = query.filter(Income.enrollment_id == enrollment_id)
        if income_type:
            query = query.filter(Income.income_type == income_type)
        if payment_method:
            query = query.filter(Income.payment_method.in_(self._payment_method_values(payment_method)))
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

    def list_records(self, *, student_id=None, class_id=None, enrollment_id=None, income_type=None,
                     payment_method=None, payment_period=None, date_from=None, date_to=None,
                     search_text=None, offset: int = 0, limit: int = 20, finance_period_start=None,
                     status: Optional[str] = Income.STATUS_ACTIVE, sort_by: str = "payment_date",
                     ascending: bool = False) -> List[Income]:
        query = self._session.query(Income).options(*self._load_options())
        query = self._apply_filters(
            query, student_id=student_id, class_id=class_id, enrollment_id=enrollment_id,
            income_type=income_type, payment_method=payment_method, payment_period=payment_period,
            date_from=date_from, date_to=date_to, search_text=search_text,
            finance_period_start=finance_period_start, status=status,
        )
        sort_column = self._SORT_COLUMNS.get(sort_by, Income.payment_date)
        primary_order = asc(sort_column) if ascending else desc(sort_column)
        return query.order_by(primary_order, desc(Income.created_at), desc(Income.id)).offset(max(0, offset)).limit(max(1, limit)).all()

    def count_records(self, *, student_id=None, class_id=None, enrollment_id=None, income_type=None,
                      payment_method=None, payment_period=None, date_from=None, date_to=None,
                      search_text=None, finance_period_start=None,
                      status: Optional[str] = Income.STATUS_ACTIVE) -> int:
        query = self._session.query(Income)
        query = self._apply_filters(
            query, student_id=student_id, class_id=class_id, enrollment_id=enrollment_id,
            income_type=income_type, payment_method=payment_method, payment_period=payment_period,
            date_from=date_from, date_to=date_to, search_text=search_text,
            finance_period_start=finance_period_start, status=status,
        )
        return query.count()

    def list_active(self, student_id=None, class_id=None, income_type=None, payment_method=None,
                    payment_period=None, date_from=None, date_to=None, search_text=None,
                    offset: int = 0, limit: int = 20, finance_period_start=None,
                    sort_by: str = "payment_date", ascending: bool = False) -> List[Income]:
        return self.list_records(
            student_id=student_id, class_id=class_id, income_type=income_type,
            payment_method=payment_method, payment_period=payment_period, date_from=date_from,
            date_to=date_to, search_text=search_text, offset=offset, limit=limit,
            finance_period_start=finance_period_start, status=Income.STATUS_ACTIVE,
            sort_by=sort_by, ascending=ascending,
        )

    def count_active(self, student_id=None, class_id=None, income_type=None, payment_method=None,
                     payment_period=None, date_from=None, date_to=None, search_text=None,
                     finance_period_start=None) -> int:
        return self.count_records(
            student_id=student_id, class_id=class_id, income_type=income_type,
            payment_method=payment_method, payment_period=payment_period, date_from=date_from,
            date_to=date_to, search_text=search_text, finance_period_start=finance_period_start,
            status=Income.STATUS_ACTIVE,
        )

    def list_unattributed_tuition(self, *, student_id=None, class_id=None) -> List[Income]:
        query = self._session.query(Income).options(*self._load_options()).filter(
            Income.deleted_at.is_(None), Income.income_type == "Tuition", Income.enrollment_id.is_(None)
        )
        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        return query.order_by(asc(Income.payment_date), asc(Income.id)).all()

    @staticmethod
    def _decimal(value) -> Decimal:
        return Decimal(str(value or 0))

    def list_active_tuition_settlement_components(
        self,
        enrollment_id: int,
        *,
        as_of_date: Optional[date] = None,
    ) -> Tuple[TuitionSettlementComponent, ...]:
        """Return the canonical signed components used to compute settled tuition.

        Cash/bank refunds are represented by their negative Income row. REFUND
        TuitionAdjustment rows are intentionally excluded because each is linked
        to that Income and including both would double-count the refund.
        """
        payment_query = self._session.query(Income).filter(
            Income.deleted_at.is_(None),
            Income.status == Income.STATUS_ACTIVE,
            Income.income_type == "Tuition",
            Income.enrollment_id == enrollment_id,
        )
        if as_of_date is not None:
            payment_query = payment_query.filter(Income.payment_date <= as_of_date)

        components = []
        for income in payment_query.all():
            amount = self._decimal(income.amount)
            components.append(
                TuitionSettlementComponent(
                    kind=(
                        TuitionSettlementComponent.KIND_REFUND
                        if amount < 0
                        else TuitionSettlementComponent.KIND_PAYMENT
                    ),
                    source=TuitionSettlementComponent.SOURCE_INCOME,
                    source_id=int(income.id),
                    effective_date=income.payment_date,
                    amount=amount,
                    wallet=income.payment_method,
                    note=income.note,
                )
            )

        credit_query = self._session.query(TuitionAdjustment).filter(
            TuitionAdjustment.kind == TuitionAdjustment.KIND_CREDIT,
            TuitionAdjustment.enrollment_id == enrollment_id,
        )
        if as_of_date is not None:
            credit_query = credit_query.filter(TuitionAdjustment.adjustment_date <= as_of_date)
        for adjustment in credit_query.all():
            components.append(
                TuitionSettlementComponent(
                    kind=TuitionSettlementComponent.KIND_CREDIT_ADJUSTMENT,
                    source=TuitionSettlementComponent.SOURCE_ADJUSTMENT,
                    source_id=int(adjustment.id),
                    effective_date=adjustment.adjustment_date,
                    amount=self._decimal(adjustment.amount),
                    note=adjustment.reason,
                )
            )

        incoming_query = self._session.query(EnrollmentTransfer).filter(
            EnrollmentTransfer.target_enrollment_id == enrollment_id,
            EnrollmentTransfer.transferred_credit != 0,
        )
        outgoing_query = self._session.query(EnrollmentTransfer).filter(
            EnrollmentTransfer.source_enrollment_id == enrollment_id,
            EnrollmentTransfer.transferred_credit != 0,
        )
        if as_of_date is not None:
            cutoff = datetime.combine(as_of_date, time.max)
            incoming_query = incoming_query.filter(EnrollmentTransfer.transferred_at <= cutoff)
            outgoing_query = outgoing_query.filter(EnrollmentTransfer.transferred_at <= cutoff)

        for transfer in incoming_query.all():
            components.append(
                TuitionSettlementComponent(
                    kind=TuitionSettlementComponent.KIND_TRANSFER_IN,
                    source=TuitionSettlementComponent.SOURCE_TRANSFER,
                    source_id=int(transfer.id),
                    effective_date=transfer.transferred_at.date(),
                    amount=self._decimal(transfer.transferred_credit),
                    note=transfer.reason,
                    counterparty_enrollment_id=int(transfer.source_enrollment_id),
                )
            )
        for transfer in outgoing_query.all():
            components.append(
                TuitionSettlementComponent(
                    kind=TuitionSettlementComponent.KIND_TRANSFER_OUT,
                    source=TuitionSettlementComponent.SOURCE_TRANSFER,
                    source_id=int(transfer.id),
                    effective_date=transfer.transferred_at.date(),
                    amount=-self._decimal(transfer.transferred_credit),
                    note=transfer.reason,
                    counterparty_enrollment_id=int(transfer.target_enrollment_id),
                )
            )

        return tuple(
            sorted(
                components,
                key=lambda item: (
                    item.effective_date,
                    self._SETTLEMENT_KIND_ORDER[item.kind],
                    item.source_id,
                ),
            )
        )

    def sum_active_tuition_for_enrollment(self, enrollment_id: int, *, as_of_date: Optional[date] = None) -> Decimal:
        """Effective settled tuition derived from the canonical settlement components."""
        return sum(
            (
                component.amount
                for component in self.list_active_tuition_settlement_components(
                    enrollment_id,
                    as_of_date=as_of_date,
                )
            ),
            Decimal("0"),
        )

    def aggregate_active_tuition_by_student_class(self, *, finance_period_start: date, date_from: date,
                                                  date_to: date, income_type: str = "Tuition",
                                                  student_id=None, class_id=None):
        query = self._session.query(
            Income.student_id, Income.class_id, func.coalesce(func.sum(Income.amount), 0)
        ).filter(
            Income.deleted_at.is_(None), Income.status == Income.STATUS_ACTIVE,
            Income.income_type == income_type, Income.finance_period_start == finance_period_start,
            Income.payment_date >= date_from, Income.payment_date <= date_to,
            Income.student_id.isnot(None), Income.class_id.isnot(None),
        )
        if student_id is not None:
            query = query.filter(Income.student_id == student_id)
        if class_id is not None:
            query = query.filter(Income.class_id == class_id)
        return query.group_by(Income.student_id, Income.class_id).all()

    def aggregate_active_amounts_by_payment_method(self, *, finance_period_start: date,
                                                   date_from: date, date_to: date):
        return self._session.query(
            Income.payment_method, func.coalesce(func.sum(Income.amount), 0)
        ).filter(
            Income.deleted_at.is_(None), Income.status == Income.STATUS_ACTIVE,
            Income.finance_period_start == finance_period_start,
            Income.payment_date >= date_from, Income.payment_date <= date_to,
        ).group_by(Income.payment_method).all()

    def delete(self, income: Income) -> None:
        income.deleted_at = datetime.now()
