# -*- coding: utf-8 -*-
"""Business logic for Income transactions."""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.core.wallet import WalletMappingError, canonical_wallet_value
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.models.enrollment import Enrollment
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.models.income import Income
from centermanager.models.timeline_event import TimelineEventType
from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)
from centermanager.services.audit_service import AuditService
from centermanager.services.class_service import ClassService
from centermanager.services.finance_ledger_guard import (
    FinanceLedgerGuard,
    FinancePeriodClosedError,
)
from centermanager.services.permission_service import PermissionService
from centermanager.services.student_service import StudentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.tuition_accrual_service import (
    TuitionAccrualService,
    TuitionAccrualUnresolvedError,
)


_LOGGER = logging.getLogger(__name__)


class IncomeServiceError(Exception):
    pass


class IncomeNotFoundError(IncomeServiceError):
    pass


class IncomeValidationError(IncomeServiceError):
    pass


@dataclass(frozen=True)
class TuitionEnrollmentChoice:
    enrollment_id: int
    student_id: int
    student_name: str
    student_code: str
    class_id: int
    class_name: str
    course_name: Optional[str]
    enrollment_status: str
    outstanding: Decimal
    balance_state: str
    tuition_configured: bool
    student_status: str = "ACTIVE"
    class_archived: bool = False

    @property
    def debt_amount(self) -> Decimal:
        return max(self.outstanding, Decimal("0"))

    @property
    def prepaid_amount(self) -> Decimal:
        return max(-self.outstanding, Decimal("0"))


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

    def _validate_income_ownership(
        self,
        income_type,
        student_id,
        class_id,
        enrollment_id=None,
    ):
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
        if income_type != "Tuition" and enrollment_id is not None:
            raise IncomeValidationError(
                "Enrollment attribution is only valid for Tuition income."
            )

    def _validate_income_type(self, income_type: str) -> str:
        valid = ["Tuition", "Book", "Robot Kit", "Material", "Other"]
        if income_type not in valid:
            raise IncomeValidationError(
                f"Income type must be one of: {', '.join(valid)}"
            )
        return income_type

    def _validate_payment_method(self, payment_method: str) -> str:
        try:
            return canonical_wallet_value(payment_method)
        except WalletMappingError as exc:
            raise IncomeValidationError(str(exc)) from exc

    def _validate_status(self, status: Optional[str]) -> Optional[str]:
        normalized = (status or Income.STATUS_ACTIVE).upper()
        if normalized not in self.VALID_STATUSES:
            raise IncomeValidationError(
                f"Income status must be one of: {', '.join(sorted(self.VALID_STATUSES))}"
            )
        return None if normalized == "ALL" else normalized

    @staticmethod
    def is_realized(income: Income, *, as_of: Optional[date] = None) -> bool:
        if income.deleted_at is not None or income.status != Income.STATUS_ACTIVE:
            return False
        if income.payment_date is None:
            return False
        cutoff = as_of or get_clock().today()
        return income.payment_date <= cutoff

    def _check_student_enrolled_on(
        self,
        session,
        student_id: int,
        class_id: int,
        payment_date: date,
    ) -> bool:
        """Legacy non-Tuition ownership check; Tuition uses Enrollment identity."""
        repo = self._repository_provider.enrollments(session)
        return repo.exists_on_date(student_id, class_id, payment_date)

    def _resolve_tuition_enrollment(
        self,
        session,
        *,
        student_id: int,
        class_id: int,
        enrollment_id: Optional[int],
    ) -> Enrollment:
        """Resolve one exact tuition contract without using payment_date."""
        repo = self._repository_provider.enrollments(session)
        if enrollment_id is not None:
            enrollment = repo.get_by_id(enrollment_id)
            if enrollment is None:
                raise IncomeValidationError(
                    f"Enrollment with id {enrollment_id} was not found."
                )
            if enrollment.student_id != student_id or enrollment.class_id != class_id:
                raise IncomeValidationError(
                    "Selected Enrollment does not belong to the selected Student and Class."
                )
            if getattr(enrollment, "reconciled_into_enrollment_id", None) is not None:
                raise IncomeValidationError(
                    "Selected Enrollment has been reconciled into "
                    f"Enrollment #{enrollment.reconciled_into_enrollment_id}; "
                    "use the canonical Enrollment."
                )
            return enrollment

        candidates = repo.get_by_student_and_class(student_id, class_id)
        if not candidates:
            raise IncomeValidationError(
                "No Enrollment contract exists for the selected Student and Class."
            )
        if len(candidates) > 1:
            raise IncomeValidationError(
                "Multiple Enrollment contracts exist for this Student and Class; "
                "select the exact Enrollment."
            )
        return candidates[0]

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

    def _ensure_period_start_mutable(self, session, period_start: date) -> None:
        try:
            FinanceLedgerGuard.ensure_period_start_mutable(
                session, self._repository_provider, period_start
            )
        except FinancePeriodClosedError as exc:
            raise IncomeValidationError(str(exc)) from exc

    def _ensure_income_period_mutable(self, session, income: Income) -> None:
        if income.finance_period_start is not None:
            self._ensure_period_start_mutable(session, income.finance_period_start)
        try:
            resolved = FinanceLedgerGuard.resolve_period(
                session, self._repository_provider, income.payment_date
            )
            if income.finance_period_start != resolved.period_start:
                self._ensure_period_start_mutable(session, resolved.period_start)
        except (FinancePeriodClosedError, ValueError) as exc:
            raise IncomeValidationError(str(exc)) from exc

    @staticmethod
    def _validate_realized_posting_date(payment_date: date) -> None:
        if payment_date > get_clock().today():
            raise IncomeValidationError(
                "ACTIVE income cannot be posted with a future payment date."
            )

    @staticmethod
    def _audit_snapshot(income: Income) -> dict:
        return {
            "student_id": income.student_id,
            "class_id": income.class_id,
            "enrollment_id": income.enrollment_id,
            "amount": income.amount,
            "income_type": income.income_type,
            "payment_method": income.payment_method,
            "payment_date": income.payment_date.isoformat() if income.payment_date else None,
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
            details={"old_values": old_values, "new_values": new_values},
            actor=get_current_user(),
            entity_type="Income",
            entity_id=income.id,
            summary=f"{action}: Income#{income.id}",
        )

    def _best_effort_timeline_event(self, **kwargs) -> None:
        try:
            self._timeline_service.log_event(**kwargs)
        except Exception:
            _LOGGER.exception(
                "Income mutation committed but timeline projection failed "
                "(income_id=%s).",
                kwargs.get("metadata", {}).get("income_id"),
            )

    def _tuition_choice_from_enrollment(
        self,
        session,
        enrollment: Enrollment,
    ) -> TuitionEnrollmentChoice:
        student = enrollment.student or self._repository_provider.students(session).get_by_id(
            enrollment.student_id
        )
        class_obj = enrollment.class_ or self._repository_provider.classes(session).get_by_id(
            enrollment.class_id
        )
        configured = bool(enrollment.has_tuition_contract)
        accrued = Decimal("0")
        if configured:
            try:
                accrual = TuitionAccrualService.calculate_from_records(
                    enrollment,
                    self._repository_provider.sessions(session).get_by_class(
                        enrollment.class_id
                    ),
                    get_clock().today(),
                )
                accrued = Decimal(str(accrual.net_accrued or 0))
            except TuitionAccrualUnresolvedError:
                configured = False

        paid = Decimal(
            str(
                self._repository_provider.incomes(
                    session
                ).sum_active_tuition_for_enrollment(
                    int(enrollment.id),
                    as_of_date=get_clock().today(),
                )
                or 0
            )
        )
        outstanding = accrued - paid
        if not configured:
            balance_state = "NO_TUITION_CONFIGURED"
        elif outstanding > 0:
            balance_state = "OWED"
        elif outstanding < 0:
            balance_state = "PREPAID"
        else:
            balance_state = "PAID"

        return TuitionEnrollmentChoice(
            enrollment_id=int(enrollment.id),
            student_id=int(enrollment.student_id),
            student_name=student.full_name,
            student_code=student.student_code,
            class_id=int(enrollment.class_id),
            class_name=class_obj.name,
            course_name=enrollment.course_name or class_obj.course,
            enrollment_status=enrollment.status,
            outstanding=outstanding,
            balance_state=balance_state,
            tuition_configured=configured,
            student_status=getattr(student, "status", "ACTIVE") or "ACTIVE",
            class_archived=getattr(class_obj, "deleted_at", None) is not None,
        )

    @require_permission("finance.view")
    def search_tuition_enrollment_choices(
        self,
        query: str = "",
        *,
        mode: str = "ACTIVE",
        limit: int = 20,
    ) -> List[TuitionEnrollmentChoice]:
        """Search exact tuition contracts for Income entry.

        ACTIVE is the operational default. OLD_DEBT intentionally includes
        archived Students/Classes, then keeps only historical contracts whose
        canonical signed tuition balance is still positive (money owed).
        """
        normalized_mode = (mode or "ACTIVE").upper()
        if normalized_mode not in {"ACTIVE", "OLD_DEBT", "ALL"}:
            raise IncomeValidationError(f"Unsupported tuition picker mode: {mode}")

        repository_limit = int(limit)
        if normalized_mode == "OLD_DEBT":
            # Debt filtering happens after canonical accrual/settlement projection.
            # Fetch a bounded wider candidate window so settled history does not
            # crowd debt rows out of the first visible results.
            repository_limit = min(max(int(limit) * 5, 50), 100)

        with self._session_factory() as session:
            enrollments = self._repository_provider.enrollments(
                session
            ).search_tuition_payment_candidates(
                query,
                mode=normalized_mode,
                limit=repository_limit,
            )
            choices = [
                self._tuition_choice_from_enrollment(session, enrollment)
                for enrollment in enrollments
            ]

        if normalized_mode == "OLD_DEBT":
            choices = [
                choice
                for choice in choices
                if choice.enrollment_status in {"WITHDRAWN", "COMPLETED"}
                and choice.tuition_configured
                and choice.debt_amount > 0
            ]
            choices.sort(
                key=lambda choice: (
                    -choice.debt_amount,
                    choice.student_name.casefold(),
                    choice.class_name.casefold(),
                    -choice.enrollment_id,
                )
            )

        return choices[: max(1, int(limit))]

    @require_permission("finance.view")
    def list_tuition_enrollments(self, student_id: int, class_id: int) -> List[Enrollment]:
        with self._session_factory() as session:
            return self._repository_provider.enrollments(session).get_by_student_and_class(
                student_id, class_id
            )

    @require_permission("finance.view")
    def list_unattributed_tuition(
        self,
        *,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
    ) -> List[Income]:
        with self._session_factory() as session:
            return self._repository_provider.incomes(session).list_unattributed_tuition(
                student_id=student_id,
                class_id=class_id,
            )

    @require_permission("finance.view")
    def get_tuition_paid_for_enrollment(
        self,
        enrollment_id: int,
        *,
        as_of_date: Optional[date] = None,
    ) -> Decimal:
        with self._session_factory() as session:
            enrollment = self._repository_provider.enrollments(session).get_by_id(enrollment_id)
            if enrollment is None:
                raise IncomeValidationError(f"Enrollment with id {enrollment_id} was not found.")
            return self._repository_provider.incomes(session).sum_active_tuition_for_enrollment(
                enrollment_id,
                as_of_date=as_of_date,
            )

    @require_permission("finance.income.create")
    def _class_name_for_tuition(self, class_id: int) -> str:
        """Read class name for historical Tuition without reopening class mutations.

        ClassService.get_class() intentionally excludes archived classes.
        Tuition collection remains permitted for an existing Enrollment.
        """
        with self._session_factory() as session:
            class_record = self._repository_provider.classes(session).get_by_id(class_id)
            if class_record is None:
                raise IncomeValidationError(
                    f"Class #{class_id} was not found for the tuition enrollment."
                )
            return class_record.name

    def create_income(
        self,
        amount: float,
        income_type: str,
        payment_method: str,
        payment_date: date,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        enrollment_id: Optional[int] = None,
        payment_period: Optional[str] = None,
        received_by: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Income:
        amount = self._validate_amount(amount)
        income_type = self._validate_income_type(income_type)
        payment_method = self._validate_payment_method(payment_method)
        self._validate_income_ownership(income_type, student_id, class_id, enrollment_id)
        if payment_date is None:
            raise IncomeValidationError("Payment date is required.")
        self._validate_realized_posting_date(payment_date)

        payment_period = self._normalize_text(payment_period)
        _, actor_name = self._actor()
        received_by = self._normalize_text(received_by) or actor_name
        note = self._normalize_text(note)

        class_name = "N/A"
        if student_id is not None:
            self._student_service.get_student(student_id)
        if class_id is not None:
            if income_type == "Tuition":
                class_name = self._class_name_for_tuition(class_id)
            else:
                class_record = self._class_service.get_class(class_id)
                class_name = class_record.name

        with self._session_factory() as session:
            resolved_enrollment = None
            if income_type == "Tuition":
                resolved_enrollment = self._resolve_tuition_enrollment(
                    session,
                    student_id=int(student_id),
                    class_id=int(class_id),
                    enrollment_id=enrollment_id,
                )
            elif (
                student_id is not None
                and class_id is not None
                and not self._check_student_enrolled_on(session, student_id, class_id, payment_date)
            ):
                raise IncomeValidationError(
                    "Student was not enrolled in the selected class on the payment date."
                )

            repo = self._repository_provider.incomes(session)
            finance_period, finance_period_start = self._resolve_finance_period(session, payment_date)
            self._ensure_period_start_mutable(session, finance_period_start)
            income = Income(
                student_id=student_id,
                class_id=class_id,
                enrollment_id=resolved_enrollment.id if resolved_enrollment is not None else None,
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
            self._record_audit(session, income, "CREATE", new_values=self._audit_snapshot(income))
            session.commit()
            repo.refresh(income)

            if student_id is not None:
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
                        "enrollment_id": income.enrollment_id,
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

    @require_permission("finance.income.create")
    def create_tuition_payment_with_credit(
        self,
        *,
        student_id: int,
        class_id: int,
        enrollment_id: int,
        amount: float,
        payment_method: str,
        payment_date: date,
        credit_amount,
        credit_reason: str,
        payment_period: Optional[str] = None,
        received_by: Optional[str] = None,
        note: Optional[str] = None,
    ) -> tuple[Income, TuitionAdjustment]:
        """Atomically post actual cash/bank received plus one non-cash tuition credit.

        The Income amount is always the real money received. The credit adjustment
        settles the remaining tuition obligation without creating a fake wallet
        movement, so accounting cash and tuition settlement stay reconcilable.
        """
        amount = self._validate_amount(amount)
        payment_method = self._validate_payment_method(payment_method)
        if payment_date is None:
            raise IncomeValidationError("Payment date is required.")
        self._validate_realized_posting_date(payment_date)
        try:
            resolved_credit = Decimal(str(credit_amount or 0)).quantize(Decimal("0.01"))
        except Exception as exc:
            raise IncomeValidationError("Tuition credit amount must be a valid number.") from exc
        if resolved_credit <= 0:
            raise IncomeValidationError("Tuition credit amount must be greater than 0.")
        resolved_reason = (credit_reason or "").strip()
        if not resolved_reason:
            raise IncomeValidationError("A reason is required for a non-cash tuition credit.")

        payment_period = self._normalize_text(payment_period)
        _, actor_name = self._actor()
        actor = get_current_user()
        received_by = self._normalize_text(received_by) or actor_name
        note = self._normalize_text(note)

        self._student_service.get_student(student_id)
        class_name = self._class_name_for_tuition(class_id)

        with self._session_factory() as session:
            enrollment = self._resolve_tuition_enrollment(
                session,
                student_id=int(student_id),
                class_id=int(class_id),
                enrollment_id=int(enrollment_id),
            )
            finance_period, finance_period_start = self._resolve_finance_period(
                session,
                payment_date,
            )
            self._ensure_period_start_mutable(session, finance_period_start)

            income_repo = self._repository_provider.incomes(session)
            adjustment_repo = self._repository_provider.tuition_adjustments(session)

            income = Income(
                student_id=student_id,
                class_id=class_id,
                enrollment_id=enrollment.id,
                amount=amount,
                income_type="Tuition",
                payment_method=payment_method,
                payment_date=payment_date,
                payment_period=payment_period,
                finance_period_id=finance_period.id,
                finance_period_start=finance_period_start,
                received_by=received_by,
                note=note,
                status=Income.STATUS_ACTIVE,
            )
            income_repo.add(income)
            income_repo.flush()

            adjustment = TuitionAdjustment(
                enrollment_id=enrollment.id,
                origin_income_id=None,
                origin_adjustment_id=None,
                linked_income_id=None,
                kind=TuitionAdjustment.KIND_CREDIT,
                amount=resolved_credit,
                adjustment_date=payment_date,
                wallet=None,
                reason=resolved_reason,
                idempotency_key=f"tuition-payment-credit:{uuid4()}",
                created_by=getattr(actor, "username", None),
            )
            adjustment_repo.add(adjustment)
            adjustment_repo.flush()

            self._record_audit(
                session,
                income,
                "CREATE",
                new_values=self._audit_snapshot(income),
            )
            self._audit_service.record_in_session(
                session,
                action="TUITION_CREDIT_ADJUSTMENT",
                module="tuition",
                target_type="tuition_adjustment",
                target_id=adjustment.id,
                target_name=f"Tuition Credit Adjustment #{adjustment.id}",
                actor=actor,
                details={
                    "enrollment_id": enrollment.id,
                    "linked_income_id": income.id,
                    "amount": str(resolved_credit),
                    "adjustment_date": payment_date.isoformat(),
                    "accounting_period_start": finance_period_start.isoformat(),
                    "wallet_movement": False,
                    "reason": resolved_reason,
                    "source": "PAYMENT_TIME_DISCOUNT",
                },
                entity_type="TuitionAdjustment",
                entity_id=adjustment.id,
                summary=f"Payment-time tuition credit for Enrollment#{enrollment.id}",
            )

            # Snapshot event/audit identities before commit expires ORM state.
            event_income_id = int(income.id)
            event_adjustment_id = int(adjustment.id)
            event_enrollment_id = int(enrollment.id)
            event_finance_period_id = int(finance_period.id)
            event_finance_period_start = finance_period_start

            session.commit()
            income_repo.refresh(income)
            adjustment_repo.refresh(adjustment)

        self._best_effort_timeline_event(
            student_id=student_id,
            event_type=TimelineEventType.INCOME_CREATED,
            title="Tuition Payment Recorded",
            description=(
                f"Actual received: {amount:,.0f} VND; non-cash tuition credit: "
                f"{resolved_credit:,.0f} VND; Method: {payment_method}; "
                f"Class: {class_name}"
            ),
            metadata={
                "income_id": event_income_id,
                "class_id": class_id,
                "enrollment_id": event_enrollment_id,
                "amount": amount,
                "non_cash_credit": str(resolved_credit),
                "payment_method": payment_method,
                "finance_period_id": event_finance_period_id,
                "finance_period_start": event_finance_period_start.isoformat(),
            },
        )
        self._publish_finance_change("created", event_income_id)
        if self._event_bus is not None:
            self._event_bus.publish(
                FinanceDataChanged(
                    entity="tuition_adjustment",
                    action="credit_adjustment",
                    entity_id=event_adjustment_id,
                )
            )
        return income, adjustment


    @require_permission("finance.view")
    def get_income(self, income_id: int) -> Income:
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id(income_id)
            if income is None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found.")
            return income

    @require_permission("finance.view")
    def list_incomes(
        self,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        enrollment_id: Optional[int] = None,
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
                enrollment_id=enrollment_id,
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

    @require_permission("finance.view")
    def sum_incomes(
        self,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        enrollment_id: Optional[int] = None,
        income_type: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_period: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search_text: Optional[str] = None,
        finance_period_start: Optional[date] = None,
        status: Optional[str] = Income.STATUS_ACTIVE,
    ) -> Decimal:
        normalized_status = self._validate_status(status)
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            return repo.sum_records(
                student_id=student_id,
                class_id=class_id,
                enrollment_id=enrollment_id,
                income_type=income_type,
                payment_method=payment_method,
                payment_period=payment_period,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
                finance_period_start=finance_period_start,
                status=normalized_status,
            )

    @require_permission("finance.income.update")
    def reconcile_tuition_enrollment(self, income_id: int, enrollment_id: int) -> Income:
        """Explicitly link one legacy Tuition row; never infer/backfill silently."""
        with self._session_factory() as session:
            income_repo = self._repository_provider.incomes(session)
            income = income_repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found.")
            if income.income_type != "Tuition":
                raise IncomeValidationError("Only Tuition income can be reconciled.")
            if income.student_id is None or income.class_id is None:
                raise IncomeValidationError("Legacy Tuition row is missing Student/Class identity.")
            if income.enrollment_id is not None:
                if income.enrollment_id == enrollment_id:
                    return income
                raise IncomeValidationError(
                    "Tuition income is already linked to a different Enrollment."
                )

            enrollment = self._resolve_tuition_enrollment(
                session,
                student_id=income.student_id,
                class_id=income.class_id,
                enrollment_id=enrollment_id,
            )
            before = self._audit_snapshot(income)
            income.enrollment_id = enrollment.id
            after = self._audit_snapshot(income)
            self._record_audit(
                session,
                income,
                "TUITION_ENROLLMENT_RECONCILE",
                old_values=before,
                new_values=after,
            )
            session.commit()
            income_repo.refresh(income)
            self._publish_finance_change("tuition_reconciled", income.id)
            return income

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
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found or deleted.")
            if income.status != Income.STATUS_ACTIVE:
                raise IncomeValidationError("Only ACTIVE income can be edited.")

            self._ensure_income_period_mutable(session, income)
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
                    changed.append(f"payment_method: {income.payment_method} -> {payment_method}")
                    income.payment_method = payment_method

            if payment_date is not None and income.payment_date != payment_date:
                self._validate_realized_posting_date(payment_date)
                changed.append(f"payment_date: {income.payment_date} -> {payment_date}")
                income.payment_date = payment_date
            else:
                self._validate_realized_posting_date(income.payment_date)

            if (
                income.income_type != "Tuition"
                and income.student_id is not None
                and income.class_id is not None
                and not self._check_student_enrolled_on(
                    session, income.student_id, income.class_id, income.payment_date
                )
            ):
                raise IncomeValidationError(
                    "Student was not enrolled in the selected class on the payment date."
                )

            finance_period, new_period_start = self._resolve_finance_period(session, income.payment_date)
            self._ensure_period_start_mutable(session, new_period_start)
            if income.finance_period_id != finance_period.id:
                changed.append(f"finance_period_id: {income.finance_period_id} -> {finance_period.id}")
                income.finance_period_id = finance_period.id
            if income.finance_period_start != new_period_start:
                changed.append(
                    f"finance_period_start: {income.finance_period_start} -> {new_period_start}"
                )
                income.finance_period_start = new_period_start

            if payment_period is not None:
                new_period = self._normalize_text(payment_period)
                if income.payment_period != new_period:
                    changed.append(
                        f"payment_period: {income.payment_period or '(none)'} -> {new_period or '(none)'}"
                    )
                    income.payment_period = new_period

            if received_by is not None:
                new_received_by = self._normalize_text(received_by) or "System"
                if income.received_by != new_received_by:
                    changed.append(f"received_by: {income.received_by} -> {new_received_by}")
                    income.received_by = new_received_by

            if note is not None:
                new_note = self._normalize_text(note)
                if income.note != new_note:
                    changed.append(f"note: {income.note or '(none)'} -> {new_note or '(none)'}")
                    income.note = new_note

            if not changed:
                return income

            after = self._audit_snapshot(income)
            self._record_audit(session, income, "UPDATE", old_values=before, new_values=after)
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
                raise IncomeNotFoundError(f"Income with id {income_id} not found or deleted.")
            if income.status != Income.STATUS_ACTIVE:
                raise IncomeValidationError("Only ACTIVE income can be voided.")
            self._ensure_income_period_mutable(session, income)
            before = self._audit_snapshot(income)
            _, actor_name = self._actor()
            income.status = Income.STATUS_VOIDED
            income.voided_at = datetime.now()
            income.voided_by = actor_name
            income.void_reason = reason
            after = self._audit_snapshot(income)
            self._record_audit(session, income, "VOID", old_values=before, new_values=after)
            session.commit()
            repo.refresh(income)
            if income.student_id is not None:
                self._best_effort_timeline_event(
                    student_id=income.student_id,
                    event_type=TimelineEventType.INCOME_UPDATED,
                    title="Income Voided",
                    description=f"Income voided. Reason: {reason}",
                    metadata={"income_id": income.id, "reason": reason, "voided_by": actor_name},
                )
            self._publish_finance_change("voided", income.id)
            return income

    @require_permission("finance.income.delete")
    def delete_income(self, income_id: int) -> None:
        with self._session_factory() as session:
            repo = self._repository_provider.incomes(session)
            income = repo.get_by_id_including_deleted(income_id)
            if income is None or income.deleted_at is not None:
                raise IncomeNotFoundError(f"Income with id {income_id} not found or already deleted.")
            self._ensure_income_period_mutable(session, income)
            before = self._audit_snapshot(income)
            student_id = income.student_id
            income.deleted_at = datetime.now()
            after = self._audit_snapshot(income)
            self._record_audit(session, income, "DELETE", old_values=before, new_values=after)
            session.commit()
            if student_id is not None:
                self._best_effort_timeline_event(
                    student_id=student_id,
                    event_type=TimelineEventType.INCOME_DELETED,
                    title="Income Deleted",
                    description=f"Income {income.income_type} amount {income.amount:,.0f} VND deleted.",
                    metadata={"income_id": income_id},
                )
            self._publish_finance_change("deleted", income_id)

    @require_permission("finance.view")
    def export_incomes_csv(
        self,
        *,
        student_id: Optional[int] = None,
        class_id: Optional[int] = None,
        enrollment_id: Optional[int] = None,
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
                enrollment_id=enrollment_id,
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
        writer.writerow([
            "Payment Date", "Source", "Student", "Class", "Enrollment ID",
            "Tuition Attribution", "Income Type", "Amount", "Payment Method",
            "Payment Period", "Finance Period Start", "Received By", "Note",
            "Status", "Voided At", "Voided By", "Void Reason",
        ])
        for income in records:
            linked = income.student_id is not None
            writer.writerow([
                income.payment_date.isoformat(),
                "STUDENT_PAYMENT" if linked else "OTHER_INCOME",
                income.student.full_name if linked and income.student else "",
                income.class_.name if linked and income.class_ else "",
                income.enrollment_id or "",
                income.tuition_attribution_status,
                income.income_type,
                income.amount,
                income.payment_method,
                income.payment_period or "",
                income.finance_period_start.isoformat() if income.finance_period_start else "",
                income.received_by or "",
                income.note or "",
                income.status,
                income.voided_at.isoformat() if income.voided_at else "",
                income.voided_by or "",
                income.void_reason or "",
            ])
        return output.getvalue()
