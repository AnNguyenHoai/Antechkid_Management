"""Bounded, query-only tuition attribution diagnostics (Phase 0B)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from centermanager.core.permission_guard import require_permission
from centermanager.dto.finance_diagnostics_dto import FinanceFinding, FinanceFindingsPage
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)


_LOGGER = logging.getLogger(__name__)
_RULES = ("D01", "D02")
_SOURCE_VERSION = "finance-diagnostics-attribution-v1"


class FinanceDiagnosticsService:
    def __init__(self, session_factory, repository_provider: RepositoryProvider | None = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    @staticmethod
    def _finding(rule_id: str, row, as_of_date: date, detected_at: datetime) -> FinanceFinding:
        if rule_id == "D01":
            count = int(row.candidate_count)
            evidence = f"Tuition Income has no Enrollment attribution; {count} canonical candidate(s)."
            canonical_id = None
            guidance = "Review the existing Enrollment reconciliation workflow; never auto-assign."
            false_positive = "A legitimate legacy payment may await explicit reconciliation."
        else:
            count = None
            canonical_id = row.canonical_enrollment_id
            evidence = (
                "Linked Enrollment is missing, has different Student/Class identity, "
                "or was reconciled into another Enrollment."
            )
            guidance = "Inspect Income, linked Enrollment and reconciliation lineage before correction."
            false_positive = "Historical lineage may explain an older link; verify before changing it."
        return FinanceFinding(
            rule_id=rule_id,
            source_version=_SOURCE_VERSION,
            as_of_date=as_of_date,
            detected_at=detected_at,
            severity="REVIEW" if rule_id == "D01" else "HIGH",
            entity_type="Income",
            entity_id=int(row.income_id),
            student_id=row.student_id,
            class_id=row.class_id,
            enrollment_id=row.enrollment_id,
            observed_amount=Decimal(str(row.amount)),
            payment_date=row.payment_date,
            evidence=evidence,
            review_guidance=guidance,
            false_positive_note=false_positive,
            candidate_count=count,
            canonical_enrollment_id=canonical_id,
            linked_student_id=None if rule_id == "D01" else row.linked_student_id,
            linked_class_id=None if rule_id == "D01" else row.linked_class_id,
        )

    @require_permission("finance.view")
    def get_findings(
        self, *, as_of_date: date, rule_id: str | None = None,
        page: int = 1, per_page: int = 50,
    ) -> FinanceFindingsPage:
        if not isinstance(as_of_date, date) or isinstance(as_of_date, datetime):
            raise ValueError("as_of_date must be a date.")
        if rule_id is not None and rule_id not in _RULES:
            raise ValueError("Unsupported diagnostics rule.")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError("page must be a positive integer.")
        if isinstance(per_page, bool) or not isinstance(per_page, int) or not 1 <= per_page <= 100:
            raise ValueError("per_page must be between 1 and 100.")

        detected_at = datetime.now(timezone.utc)
        selected = (rule_id,) if rule_id else _RULES
        try:
            with self._session_factory() as session:
                # SQLite/SQLCipher query_only rejects accidental DML even when
                # a repository is changed later. Reset before returning the
                # connection to its pool; discard it if reset cannot succeed.
                connection = session.connection()
                connection.exec_driver_sql("PRAGMA query_only = ON")
                try:
                    with session.no_autoflush:
                        repo = self._repository_provider.incomes(session)
                        counts = {
                            code: repo.count_tuition_attribution_cases(code, as_of_date)
                            for code in selected
                        }
                        offset = (page - 1) * per_page
                        findings = []
                        for code in selected:
                            count = counts[code]
                            if offset >= count:
                                offset -= count
                                continue
                            rows = repo.list_tuition_attribution_cases(
                                code, as_of_date, offset=offset,
                                limit=min(per_page - len(findings), count - offset),
                            )
                            findings.extend(
                                self._finding(code, row, as_of_date, detected_at)
                                for row in rows
                            )
                            offset = 0
                            if len(findings) == per_page:
                                break
                finally:
                    try:
                        connection.exec_driver_sql("PRAGMA query_only = OFF")
                    except Exception:
                        session.invalidate()
                        raise
                    session.rollback()
            return FinanceFindingsPage(
                state="OK", as_of_date=as_of_date, detected_at=detected_at,
                source_version=_SOURCE_VERSION, page=page, per_page=per_page,
                total_count=sum(counts.values()), counts_by_rule=counts,
                findings=tuple(findings),
            )
        except Exception as exc:
            # Do not log SQL parameters or student/family data. An error is never
            # presented as an empty, valid diagnostics result.
            _LOGGER.error("Finance diagnostics failed: %s", type(exc).__name__)
            return FinanceFindingsPage(
                state="ERROR", as_of_date=as_of_date, detected_at=detected_at,
                source_version=_SOURCE_VERSION, page=page, per_page=per_page,
                total_count=None, counts_by_rule={}, findings=(),
                error_code="DIAGNOSTICS_READ_FAILED",
            )
