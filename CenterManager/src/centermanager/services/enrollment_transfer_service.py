# -*- coding: utf-8 -*-
"""Atomic class-transfer lifecycle for Enrollment tuition contracts."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from centermanager.core.capabilities import Capability
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.enrollment import Enrollment
from centermanager.models.enrollment_transfer import EnrollmentTransfer
from centermanager.models.session import SessionStatus
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.services.audit_service import AuditService
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.tuition_accrual_service import TuitionAccrualService, TuitionAccrualUnresolvedError


class EnrollmentTransferError(Exception):
    pass


class EnrollmentTransferValidationError(EnrollmentTransferError):
    pass


_MONEY_QUANTUM = Decimal("0.0001")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class EnrollmentTransferService:
    """Creates a new target contract and preserves the source as immutable history."""

    def __init__(self, session_factory, repository_provider: Optional[RepositoryProvider] = None,
                 audit_service: Optional[AuditService] = None) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()
        self._audit_service = audit_service or AuditService(
            session_factory, repository_provider=self._repository_provider
        )

    @classmethod
    def from_enrollment_service(cls, enrollment_service):
        return cls(
            enrollment_service._session_factory,
            repository_provider=enrollment_service._repository_provider,
            audit_service=enrollment_service._audit_service,
        )

    @staticmethod
    def _require_reason(reason: str) -> str:
        resolved = (reason or "").strip()
        if not resolved:
            raise EnrollmentTransferValidationError("Transfer reason is required.")
        return resolved

    @staticmethod
    def _idempotency_key(source_enrollment_id: int, value: Optional[str]) -> str:
        key = (value or f"source-enrollment:{source_enrollment_id}").strip()
        if not key:
            raise EnrollmentTransferValidationError("Transfer idempotency key is required.")
        if len(key) > 120:
            raise EnrollmentTransferValidationError("Transfer idempotency key is too long.")
        return key

    @staticmethod
    def _target_start_session(class_obj, sessions) -> int:
        if not class_obj.has_course_contract:
            raise EnrollmentTransferValidationError("Target class tuition contract is incomplete.")
        completed = [
            int(item.session_number)
            for item in sessions
            if item.status == SessionStatus.COMPLETED.value
        ]
        start = max(completed) + 1 if completed else 1
        if start > int(class_obj.planned_sessions):
            raise EnrollmentTransferValidationError("Target class has completed all planned sessions.")
        return start

    @staticmethod
    def _target_contract(class_obj, start_session: int) -> dict:
        planned_total = int(class_obj.planned_sessions)
        remaining = planned_total - int(start_session) + 1
        fee = _money(class_obj.course_fee)
        agreed = _money(fee * Decimal(remaining) / Decimal(planned_total))
        unit_fee = _money(agreed / Decimal(remaining))
        return {
            "agreed_course_fee": agreed,
            "planned_sessions": remaining,
            "unit_fee": unit_fee,
            "enrolled_from_session": int(start_session),
            "enrolled_until_session": planned_total,
            "discount_amount": Decimal("0.0000"),
        }

    @staticmethod
    def _same_command(
        existing: EnrollmentTransfer,
        *,
        source_enrollment_id: int,
        target_class_id: int,
        transferred_credit: Decimal,
        reason: str,
        idempotency_key: str,
    ) -> bool:
        target = getattr(existing, "target_enrollment", None)
        return (
            int(existing.source_enrollment_id) == int(source_enrollment_id)
            and target is not None
            and int(target.class_id) == int(target_class_id)
            and _money(existing.transferred_credit) == transferred_credit
            and existing.reason == reason
            and existing.idempotency_key == idempotency_key
        )

    def _existing_or_conflict(
        self,
        transfer_repo,
        *,
        source_enrollment_id: int,
        target_class_id: int,
        transferred_credit: Decimal,
        reason: str,
        idempotency_key: str,
    ) -> Optional[EnrollmentTransfer]:
        command = {
            "source_enrollment_id": source_enrollment_id,
            "target_class_id": target_class_id,
            "transferred_credit": transferred_credit,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        keyed = transfer_repo.get_by_idempotency_key(idempotency_key)
        if keyed is not None:
            if self._same_command(keyed, **command):
                return keyed
            raise EnrollmentTransferValidationError(
                "Transfer idempotency key is already used by a different command."
            )
        existing = transfer_repo.get_for_source(source_enrollment_id)
        if existing is not None:
            if self._same_command(existing, **command):
                return existing
            raise EnrollmentTransferValidationError(
                "Source Enrollment has already completed a different transfer."
            )
        return None

    def _recover_conflict(
        self,
        *,
        source_enrollment_id: int,
        target_class_id: int,
        transferred_credit: Decimal,
        reason: str,
        idempotency_key: str,
    ) -> EnrollmentTransfer:
        with self._session_factory() as replay_session:
            transfer_repo = self._repository_provider.enrollment_transfers(replay_session)
            existing = self._existing_or_conflict(
                transfer_repo,
                source_enrollment_id=source_enrollment_id,
                target_class_id=target_class_id,
                transferred_credit=transferred_credit,
                reason=reason,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return existing
            enrollments = self._repository_provider.enrollments(replay_session)
            source = enrollments.get_by_id(source_enrollment_id)
            if source is not None and enrollments.exists(
                source.student_id, target_class_id, active_only=True
            ):
                raise EnrollmentTransferValidationError(
                    "Student already has an active Enrollment in target class."
                )
        raise EnrollmentTransferValidationError(
            "Concurrent Enrollment transfer conflict; retry with the same idempotency key."
        )

    def _source_balance(self, session, enrollment: Enrollment) -> Decimal:
        if enrollment.class_id is None or not enrollment.has_tuition_contract:
            raise EnrollmentTransferValidationError("Source Enrollment tuition contract is unresolved.")
        sessions = self._repository_provider.sessions(session).get_by_class(enrollment.class_id)
        try:
            accrual = TuitionAccrualService.calculate_from_records(
                enrollment, sessions, get_clock().today()
            )
        except TuitionAccrualUnresolvedError as exc:
            raise EnrollmentTransferValidationError("Source Enrollment tuition contract is unresolved.") from exc
        settled = self._repository_provider.incomes(session).sum_active_tuition_for_enrollment(
            int(enrollment.id), as_of_date=get_clock().today()
        )
        return _money(Decimal(accrual.net_accrued) - Decimal(settled))

    def preview(self, source_enrollment_id: int, target_class_id: int) -> dict:
        with self._session_factory() as session:
            source = self._repository_provider.enrollments(session).get_by_id(source_enrollment_id)
            if source is None:
                raise EnrollmentTransferValidationError("Source Enrollment not found.")
            target = self._repository_provider.classes(session).get_by_id(target_class_id)
            if target is None or target.deleted_at is not None:
                raise EnrollmentTransferValidationError("Target class not found or archived.")
            sessions = self._repository_provider.sessions(session).get_by_class(target_class_id)
            start = self._target_start_session(target, sessions)
            contract = self._target_contract(target, start)
            balance = self._source_balance(session, source)
            return {
                "source_balance": balance,
                "available_prepaid_credit": max(-balance, Decimal("0.0000")),
                "target_class_id": target_class_id,
                **contract,
            }

    def transfer(self, source_enrollment_id: int, target_class_id: int, *,
                 transferred_credit=0, reason: str, actor=None,
                 idempotency_key: Optional[str] = None) -> EnrollmentTransfer:
        resolved_reason = self._require_reason(reason)
        resolved_key = self._idempotency_key(source_enrollment_id, idempotency_key)
        resolved_actor = actor if actor is not None else get_current_user()
        if resolved_actor is not None:
            AuthorizationService.require(resolved_actor, Capability.STUDENT_UPDATE)
        credit = _money(transferred_credit)
        if credit < 0:
            raise EnrollmentTransferValidationError("Transferred credit cannot be negative.")

        with self._session_factory() as session:
            enrollments = self._repository_provider.enrollments(session)
            transfer_repo = self._repository_provider.enrollment_transfers(session)
            source, target_class = transfer_repo.acquire_command_lock(
                source_enrollment_id, target_class_id
            )

            existing = self._existing_or_conflict(
                transfer_repo,
                source_enrollment_id=source_enrollment_id,
                target_class_id=target_class_id,
                transferred_credit=credit,
                reason=resolved_reason,
                idempotency_key=resolved_key,
            )
            if existing is not None:
                return existing

            if source is None:
                raise EnrollmentTransferValidationError("Source Enrollment not found.")
            if source.status != "ACTIVE":
                raise EnrollmentTransferValidationError("Only an ACTIVE Enrollment can be transferred.")
            if source.class_id == target_class_id:
                raise EnrollmentTransferValidationError("Target class must differ from source class.")
            freeze_repo = self._repository_provider.enrollment_freezes(session)
            if freeze_repo.get_open(source_enrollment_id) is not None:
                raise EnrollmentTransferValidationError("Resume the open tuition freeze before transferring.")
            if enrollments.exists(source.student_id, target_class_id, active_only=True):
                raise EnrollmentTransferValidationError("Student already has an active Enrollment in target class.")

            if target_class is None or target_class.deleted_at is not None:
                raise EnrollmentTransferValidationError("Target class not found or archived.")
            if target_class.capacity is not None and len(
                enrollments.get_active_by_class(target_class_id)
            ) >= target_class.capacity:
                raise EnrollmentTransferValidationError(
                    f"Target class capacity ({target_class.capacity}) reached."
                )

            target_sessions = self._repository_provider.sessions(session).get_by_class(target_class_id)
            target_start = self._target_start_session(target_class, target_sessions)
            target_contract = self._target_contract(target_class, target_start)
            source_balance = self._source_balance(session, source)
            available_credit = max(-source_balance, Decimal("0.0000"))
            if credit > available_credit:
                raise EnrollmentTransferValidationError(
                    f"Transferred credit {credit} exceeds available prepaid credit {available_credit}."
                )

            today = get_clock().today()
            target = Enrollment(
                student_id=source.student_id,
                class_id=target_class_id,
                class_name=target_class.name,
                course_name=target_class.course,
                start_date=today,
                status="ACTIVE",
                **target_contract,
            )
            enrollments.add(target)
            if not transfer_repo.flush_guarded():
                return self._recover_conflict(
                    source_enrollment_id=source_enrollment_id,
                    target_class_id=target_class_id,
                    transferred_credit=credit,
                    reason=resolved_reason,
                    idempotency_key=resolved_key,
                )

            source.status = "WITHDRAWN"
            source.end_date = today
            transfer = EnrollmentTransfer(
                source_enrollment_id=int(source.id),
                target_enrollment_id=int(target.id),
                idempotency_key=resolved_key,
                transferred_credit=credit,
                source_balance_before=source_balance,
                reason=resolved_reason,
                transferred_at=get_clock().now(),
                created_by=getattr(resolved_actor, "username", None),
            )
            transfer_repo.add(transfer)
            if not transfer_repo.flush_guarded():
                return self._recover_conflict(
                    source_enrollment_id=source_enrollment_id,
                    target_class_id=target_class_id,
                    transferred_credit=credit,
                    reason=resolved_reason,
                    idempotency_key=resolved_key,
                )
            self._audit_service.record_in_session(
                session,
                action="TUITION_ENROLLMENT_TRANSFER",
                module="tuition",
                target_type="enrollment_transfer",
                target_id=transfer.id,
                target_name=f"{source.class_name} -> {target_class.name}",
                actor=resolved_actor,
                details={
                    "student_id": source.student_id,
                    "source_enrollment_id": source.id,
                    "target_enrollment_id": target.id,
                    "source_class_id": source.class_id,
                    "target_class_id": target_class_id,
                    "source_balance_before": str(source_balance),
                    "transferred_credit": str(credit),
                    "target_unit_fee": str(target.unit_fee),
                    "idempotency_key": resolved_key,
                    "reason": resolved_reason,
                },
                summary=f"Enrollment transfer from {source.class_name} to {target_class.name}",
            )
            session.commit()
            transfer_repo.refresh(transfer)
            return transfer
