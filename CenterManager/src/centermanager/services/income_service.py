# -*- coding: utf-8 -*-
"""Business logic for Income transactions."""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.models.income import Income
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)
from centermanager.services.audit_service import AuditService
from centermanager.services.class_service import ClassService
from centermanager.services.permission_service import PermissionService
from centermanager.services.student_service import StudentService
from centermanager.services.timeline_service import TimelineService


_LOGGER = logging.getLogger(__name__)


class IncomeServiceError(Exception):
    pass


class IncomeNotFoundError(IncomeServiceError):
    pass


class IncomeValidationError(IncomeServiceError):
    pass


class IncomeService:
    VALID_STATUSES = {Income.STATUS_ACTIVE, Income.STATUS_VOIDED, "ALL"}

    def __init__(
        self,
        session_factory: sessionmaker,
        student_service: StudentService,
        class_service: ClassService,
        timeline_service: TimelineService,
        permission_service: PermissionService,
        repository_provider: Optional[RepositoryProvider] = None,
        event_bus: Optional[EventBus] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._session_factory = session_factory
        self._student_service = student_service
        self._class_service = class_service
        self._timeline_service = timeline_service
        self._permission_service = permission_service
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._event_bus = event_bus
        self._audit_service = audit_service or AuditService(
            session_factory,
            repository_provider=self._repository_provider,
        )

    def _publish_finance_change(self, action: str, income_id: int) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(
                FinanceDataChanged(entity="income", action=action, entity_id=income_id)
            )

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @staticmethod
    def _actor() -> tuple[Optional[int], str]:
        user = get_current_user()
        if user is None:
            return None, "System"
        return getattr(user, "id", None), getattr(user, "full_name", None) or "System"

    def _validate_amount(self, amount: float) -> float:
        if amount <= 0:
            raise IncomeValidationError("Amount must be greater than 0.")
        return amount

    def _validate_income_ownership(self, income_type, student_id, class_id):
        if income_type == "Tuition":
            if student_id is None or class_id is None:
                raise IncomeValidationError("Tuition requires both student and class.")
        elif income_type == "Other":
            if student_id is not None or class_id is not None:
                raise IncomeValidationError("Other income must not be student linked.")
        elif (student_id is None) != (class_id is None):
            raise IncomeValidationError(
                "Student-linked income requires both student and class."
            )

    def _validate_income_type(self, income_type: str) -> str:
        valid = ["Tuition", "Book", "Robot Kit", "Material", "Other"]
        if income_type not in valid:
            raise IncomeValidationError(
                f"Income type must be one of: {', '.join(valid)}"
            )
        return income_type

    def _validate_payment_method(self, payment_method: str) -> str:
        valid = ["Cash", "Bank Transfer"]
        if payment_method not in valid:
            raise IncomeValidationError(
                f"Payment method must be one of: {', '.join(valid)}"
            )
        return payment_method

    def _validate_status(self, status: Optional[str]) -> Optional[str]:
        normalized = (status or Income.STATUS_ACTIVE).upper()
        if normalized not in self.VALID_STATUSES:
            raise IncomeValidationError(
                f"Income status must be one of: {', '.join(sorted(self.VALID_STATUSES))}"
            )
        return None if normalized == "ALL" else normalized

    @staticmethod
    def is_realized(
        income: Income,
        *,
        as_of: Optional[date] = None,
    ) -> bool:
        """Return whether an Income belongs to the realized ledger at ``as_of``.

        ACTIVE is necessary but not sufficient: legacy rows may contain future
        payment dates. Those rows remain readable but are not realized until the
        payment date is reached. VOIDED/deleted rows never contribute.
        """
        if income.deleted_at is not None or income.status != Income.STATUS_ACTIVE:
            return False
        if income.payment_date is None:
            return False
        cutoff = as_of or date.today()
        return income.payment_date <= cutoff

    def _check_student_enrolled_on(
        self,
        session,
        student_id: int,
        class_id: int,
        payment_date: date,
    ) -> bool:
        repo = self._repository_provider.enrollments(session)
        return repo.exists_on_date(student_id, class_id, payment_date)

    def _resolve_finance_period(self, session, payment_date: date):
        try:
            config = self._repository_provider.finance_periods(
                session
            ).get_unique_effective(payment_date)
        except ValueError as exc:
            raise IncomeValidationError(str(exc)) from exc
        if config is None:
            raise IncomeValidationError(
                "No Finance period configuration covers payment date "
                f"{payment_date.isoformat()}."
            )
        resolved = FinancePeriodDefinition.resolved_for_configuration(
            config, payment_date
        )
        return config, resolved.period_start

    @staticmethod
    def _validate_realized_posting_date(payment_date: date) -> None:
        if payment_date > date.today():
            raise IncomeValidationError(
                "ACTIVE income cannot be posted with a future payment date."
            )

    @staticmethod
    def _audit_snapshot(income: Income) -> dict:
        return {
            "student_id": income.student_id,
            "class_id": income.class_id,
            "amount": income.amount,
            "income_type": income.income_type,
            "payment_method": income.payment_method,
            "payment_date": (
                income.payment_date.isoformat() if income.payment_date else None
            ),
            "payment_period": income.payment_period,
            "finance_period_id": income.finance_period_id,
            "finance_period_start": (
                income.finance_period_start.isoformat()
                if income.finance_period_start
                else None
            ),
            "received_by": income.received_by,
            "note": income.note,
            "status": income.status,
            "voided_at": income.voided_at.isoformat() if income.voided_at else None,
            "voided_by": income.voided_by,
            "void_reason": income.void_reason,
            "deleted_at": income.deleted_at.isoformat() if income.deleted_at else None,
        }

    def _record_audit(
        self,
        session,
        income: Income,
        action: str,
        *,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
    ) -> None:
        self._audit_service.record_in_session(
            session,
            action=action,
            module="finance",
            target_type="income",
            target_id=income.id,
            target_name=f"Income #{income.id}",
            details={
                "old_values": old_values,
                "new_values": new_values,
            },
            actor=get_current_user(),
            entity_type="Income",
            entity_id=income.id,
            summary=f"{action}: Income#{income.id}",
        )

    def _best_effort_timeline_event(self, **kwargs) -> None:
        """Project a timeline event without invalidating a committed mutation."""
        try:
            self._timeline_service.log_event(**kwargs)
        except Exception:
            _LOGGER.exception(
                "Income mutation committed but timeline projection failed "
                "(income_id=%s).",
                kwargs.get("metadata", {}).get("income_id"),
            )

    @require_permission("finance.income.create")
    def create_income(
        self,
        amount: float,
        income_type: str,
        payment_method: str,
        payment_date: date,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        payment_period: Optional[str] = None,
        received_by: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Income:
        amount = self._validate_amount(amount)
        income_type = self._validate_income_type(income_type)
        payment_method = self._validate_payment_method(payment_method)
        self._validate_income_ownership(income_type, student_id, class_id)
        if payment_date is None:
            raise IncomeValidationError("Payment date is required.")
        self._validate_realized_posting_date(payment_date)

        payment_period = self._normalize_text(payment_period)
        _, actor_name = self._actor()
        received_by = self._normalize_text(received_by) or actor_name
        note = self._normalize_text(note)

        if student_id is not None:
            self._student_service.get_student(student_id)
        if class_id is not None:
            self._class_service.get_class(class_id)

        with self._session_factory() as session:
            if (
                student_id is not None
                and class_id is not None
                and not self._check_student_enrolled_on(
                    session, student_id, class_id, payment_date
                )
            ):
                raise IncomeValidationError(
                    "Student was not enrolled in the selected class "
                    "on the payment date."
                )

            repo = self._repository_provider.incomes(session)
            finance_period, finance_period_start = self._resolve_finance_period(
                session, payment_date
            )
            income = Income(
                student_id=student_id,
                class_id=class_id,
                amount=amount,
                income_type=income_type,
                payment_method=payment_method,
                payment_date=payment_date,
                payment_period=payment_period,
                finance_period_id=finance_period.id,
                finance_period_start=finance_period_start,
                received_by=received_by,
                note=note,
                status=Income.STATUS_ACTIVE,
            )
            repo.add(income)
            repo.flush()
            self._record_audit(
                session,
                income,
                "CREATE",
                new_values=self._audit_snapshot(income),
            )
            session.commit()
            repo.refresh(income)

            if student_id is not None:
                class_name = (
                    self._class_service.get_class(class_id).name if class_id else "N/A"
                )
                self._best_effort_timeline_event(
                    student_id=student_id,
                    event_type=TimelineEventType.INCOME_CREATED,
                    title=f"Income Created: {income_type}",
                    description=(
                        f"Amount: {amount:,.0f} VND, Method: {payment_method}, "
                        f"Class: {class_name}, Period: {finance_period_start.isoformat()}"
                    ),
                    metadata={
                        "income_id": income.id,
                        "class_id": class_id,
                        "amount": amount,
                        "income_type": income_type,
                        "payment_method": payment_method,
                        "payment_period": payment_period,
                        "finance_period_id": finance_period.id,
                        "finance_period_start": finance_period_start.isoformat(),
                    },
                )
            self._publish_finance_change("created", income.id)
            return income

    @require_permission("finance.view")
    def get_income(self, income_id: int) -> Income:
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id(income_id)
            if income is None:
                raise IncomeNotFoundError(
                    f"Income with id {income_id} not found."
                )
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
        finance_period_start: Optional[date] = None,
        status: Optional[str] = Income.STATUS_ACTIVE,
        sort_by: str = "payment_date",
        ascending: bool = False,
    ) -> Tuple[List[Income], int]:
        if page < 1:
            raise IncomeValidationError("Page must be >= 1.")
        if per_page < 1:
            raise IncomeValidationError("Per-page value must be >= 1.")
        normalized_status = self._validate_status(status)
        offset = (page - 1) * per_page

        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            common = dict(
                student_id=student_id,
                class_id=class_id,
                income_type=income_type,
                payment_method=payment_method,
                payment_period=payment_period,
                finance_period_start=finance_period_start,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
                status=normalized_status,
            )
            items = repo.list_records(
                **common,
                offset=offset,
                limit=per_page,
                sort_by=sort_by,
                ascending=ascending,
            )
            total = repo.count_records(**common)
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
        received_by: Optional[str] = None,
    ) -> Income:
        """Edit mutable transaction fields.

        Source/student/class/income_type are intentionally absent: they are
        transaction identity and cannot be silently changed after creation.
        """
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(
                    f"Income with id {income_id} not found or deleted."
                )
            if income.status != Income.STATUS_ACTIVE:
                raise IncomeValidationError("Only ACTIVE income can be edited.")

            before = self._audit_snapshot(income)
            changed = []

            if amount is not None:
                amount = self._validate_amount(amount)
                if income.amount != amount:
                    changed.append(f"amount: {income.amount} -> {amount}")
                    income.amount = amount

            if payment_method is not None:
                payment_method = self._validate_payment_method(payment_method)
                if income.payment_method != payment_method:
                    changed.append(
                        f"payment_method: {income.payment_method} -> {payment_method}"
                    )
                    income.payment_method = payment_method

            if payment_date is not None and income.payment_date != payment_date:
                self._validate_realized_posting_date(payment_date)
                changed.append(
                    f"payment_date: {income.payment_date} -> {payment_date}"
                )
                income.payment_date = payment_date
            else:
                self._validate_realized_posting_date(income.payment_date)

            if (
                income.student_id is not None
                and income.class_id is not None
                and not self._check_student_enrolled_on(
                    session,
                    income.student_id,
                    income.class_id,
                    income.payment_date,
                )
            ):
                raise IncomeValidationError(
                    "Student was not enrolled in the selected class "
                    "on the payment date."
                )

            finance_period, new_period_start = self._resolve_finance_period(
                session, income.payment_date
            )
            if income.finance_period_id != finance_period.id:
                changed.append(
                    "finance_period_id: "
                    f"{income.finance_period_id} -> {finance_period.id}"
                )
                income.finance_period_id = finance_period.id
            if income.finance_period_start != new_period_start:
                changed.append(
                    "finance_period_start: "
                    f"{income.finance_period_start} -> {new_period_start}"
                )
                income.finance_period_start = new_period_start

            if payment_period is not None:
                new_period = self._normalize_text(payment_period)
                if income.payment_period != new_period:
                    changed.append(
                        "payment_period: "
                        f"{income.payment_period or '(none)'} -> "
                        f"{new_period or '(none)'}"
                    )
                    income.payment_period = new_period

            if received_by is not None:
                new_received_by = self._normalize_text(received_by) or "System"
                if income.received_by != new_received_by:
                    changed.append(
                        f"received_by: {income.received_by} -> {new_received_by}"
                    )
                    income.received_by = new_received_by

            if note is not None:
                new_note = self._normalize_text(note)
                if income.note != new_note:
                    changed.append(
                        f"note: {income.note or '(none)'} -> {new_note or '(none)'}"
                    )
                    income.note = new_note

            if not changed:
                return income

            after = self._audit_snapshot(income)
            self._record_audit(
                session,
                income,
                "UPDATE",
                old_values=before,
                new_values=after,
            )
            session.commit()
            repo.refresh(income)

            if income.student_id is not None:
                self._best_effort_timeline_event(
                    student_id=income.student_id,
                    event_type=TimelineEventType.INCOME_UPDATED,
                    title="Income Updated",
                    description="Updated: " + "; ".join(changed),
                    metadata={"income_id": income.id, "changes": changed},
                )
            self._publish_finance_change("updated", income.id)
            return income

    @require_permission("finance.income.delete")
    def void_income(self, income_id: int, reason: str) -> Income:
        reason = self._normalize_text(reason)
        if not reason:
            raise IncomeValidationError("Void reason is required.")

        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(
                    f"Income with id {income_id} not found or deleted."
                )
            if income.status != Income.STATUS_ACTIVE:
                raise IncomeValidationError("Only ACTIVE income can be voided.")

            before = self._audit_snapshot(income)
            _, actor_name = self._actor()
            income.status = Income.STATUS_VOIDED
            income.voided_at = datetime.now()
            income.voided_by = actor_name
            income.void_reason = reason
            after = self._audit_snapshot(income)

            self._record_audit(
                session,
                income,
                "VOID",
                old_values=before,
                new_values=after,
            )
            session.commit()
            repo.refresh(income)

            if income.student_id is not None:
                self._best_effort_timeline_event(
                    student_id=income.student_id,
                    event_type=TimelineEventType.INCOME_UPDATED,
                    title="Income Voided",
                    description=f"Income voided. Reason: {reason}",
                    metadata={
                        "income_id": income.id,
                        "reason": reason,
                        "voided_by": actor_name,
                    },
                )
            self._publish_finance_change("voided", income.id)
            return income

    @require_permission("finance.income.delete")
    def delete_income(self, income_id: int) -> None:
        """Soft-delete a transaction without destroying its audit history.

        UI exposes Delete for VOIDED rows. The service remains backward compatible
        with legacy callers that soft-delete an ACTIVE row, but it never hard-deletes.
        """
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(
                    f"Income with id {income_id} not found or already deleted."
                )

            before = self._audit_snapshot(income)
            student_id = income.student_id
            income.deleted_at = datetime.now()
            after = self._audit_snapshot(income)
            self._record_audit(
                session,
                income,
                "DELETE",
                old_values=before,
                new_values=after,
            )
            session.commit()

            if student_id is not None:
                self._best_effort_timeline_event(
                    student_id=student_id,
                    event_type=TimelineEventType.INCOME_DELETED,
                    title="Income Deleted",
                    description=(
                        f"Income {income.income_type} amount "
                        f"{income.amount:,.0f} VND deleted."
                    ),
                    metadata={"income_id": income_id},
                )
            self._publish_finance_change("deleted", income_id)

    @require_permission("finance.view")
    def export_incomes_csv(
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
        sort_by: str = "payment_date",
        ascending: bool = False,
    ) -> str:
        normalized_status = self._validate_status(status)
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            common = dict(
                student_id=student_id,
                class_id=class_id,
                income_type=income_type,
                payment_method=payment_method,
                payment_period=payment_period,
                finance_period_start=finance_period_start,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
                status=normalized_status,
            )
            total = repo.count_records(**common)
            records = repo.list_records(
                **common,
                offset=0,
                limit=max(1, total),
                sort_by=sort_by,
                ascending=ascending,
            )

        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "Payment Date",
                "Source",
                "Student",
                "Class",
                "Income Type",
                "Amount",
                "Payment Method",
                "Payment Period",
                "Finance Period Start",
                "Received By",
                "Note",
                "Status",
                "Voided At",
                "Voided By",
                "Void Reason",
            ]
        )
        for income in records:
            linked = income.student_id is not None
            writer.writerow(
                [
                    income.payment_date.isoformat(),
                    "STUDENT_PAYMENT" if linked else "OTHER_INCOME",
                    income.student.full_name if linked and income.student else "",
                    income.class_.name if linked and income.class_ else "",
                    income.income_type,
                    income.amount,
                    income.payment_method,
                    income.payment_period or "",
                    (
                        income.finance_period_start.isoformat()
                        if income.finance_period_start
                        else ""
                    ),
                    income.received_by or "",
                    income.note or "",
                    income.status,
                    income.voided_at.isoformat() if income.voided_at else "",
                    income.voided_by or "",
                    income.void_reason or "",
                ]
            )
        return output.getvalue()
