# -*- coding: utf-8 -*-
"""Persistence adapter for administrator-scoped business data resets.

The repository owns SQLAlchemy metadata traversal and destructive table writes.
Application services decide authorization, backup, confirmation and auditing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

# Importing the model package registers every mapped table on Base.metadata.
import centermanager.models  # noqa: F401
from centermanager.database.base import Base


@dataclass(frozen=True)
class ResetPreviewData:
    tables: tuple[str, ...]
    counts: dict[str, int]
    blockers: dict[str, int]
    finance_counts: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.counts.values())


class AdminDataResetRepository:
    """Inspect and clear complete workspace table sets using FK-safe ordering."""

    PROTECTED_TABLES = frozenset({
        "users",
        "roles",
        "permissions",
        "role_permissions",
        "audit_logs",
    })

    FINANCE_TABLES = frozenset({
        "incomes",
        "expenses",
        "expense_timeline_events",
        "finance_periods",
        "financial_settlements",
        "tuition_adjustments",
    })

    SCOPE_TABLES = {
        "student": frozenset({
            "students", "parents", "attachments", "documents", "notes",
            "student_highlights", "student_products", "progress",
            "enrollments", "enrollment_freezes", "enrollment_transfers",
            "assessments", "attendance",
        }),
        "class": frozenset({
            "classes", "class_fee_history", "class_timeline_events",
            "teacher_assignments", "sessions", "session_notes", "attendance",
            "enrollments", "enrollment_freezes", "enrollment_transfers",
            "assessments",
        }),
        "teacher": frozenset({
            "teachers", "teacher_assignments", "teacher_documents",
            "teacher_timeline_events",
        }),
        "employee": frozenset({
            "employees", "employee_documents", "employee_schedules",
            "employee_work_registration_periods", "employee_work_registrations",
            "employee_working_times",
        }),
        "finance": FINANCE_TABLES,
        "operational": frozenset({
            "sessions", "session_notes", "attendance", "assessments",
            "reports", "report_cache", "timeline_events",
        }),
    }

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _all_tables() -> dict[str, object]:
        return dict(Base.metadata.tables)

    def resolve_tables(self, scope: str, *, include_finance: bool = False) -> tuple[str, ...]:
        normalized = str(scope or "").strip().lower()
        available = self._all_tables()
        if normalized == "all_business":
            names = set(available) - set(self.PROTECTED_TABLES)
        elif normalized in self.SCOPE_TABLES:
            expected = set(self.SCOPE_TABLES[normalized])
            # Some historical databases may not have every optional model yet;
            # operate only on tables represented by the running application's schema.
            names = expected.intersection(available)
        else:
            raise ValueError(f"Unsupported data reset scope: {scope}")

        if include_finance and normalized not in {"finance", "all_business"}:
            names.update(set(self.FINANCE_TABLES).intersection(available))
        names.difference_update(self.PROTECTED_TABLES)
        return tuple(sorted(names))

    def _count(self, table_name: str) -> int:
        table = self._all_tables()[table_name]
        return int(
            self._session.execute(select(func.count()).select_from(table)).scalar_one()
        )

    def _count_fk_references(self, table, fk_columns) -> int:
        conditions = [column.is_not(None) for column in fk_columns]
        if not conditions:
            return 0
        statement = select(func.count()).select_from(table).where(or_(*conditions))
        return int(self._session.execute(statement).scalar_one())

    def preview(self, scope: str, *, include_finance: bool = False) -> ResetPreviewData:
        selected = set(self.resolve_tables(scope, include_finance=include_finance))
        tables = self._all_tables()
        counts = {name: self._count(name) for name in sorted(selected)}

        finance_counts: dict[str, int] = {}
        for name in sorted(set(self.FINANCE_TABLES).intersection(tables)):
            count = self._count(name)
            if count:
                finance_counts[name] = count

        blockers: dict[str, int] = {}
        # Only rows whose FK value actually references a table being cleared are
        # blockers. Nullable historical/optional FK columns must not block a reset
        # merely because unrelated rows exist in the same retained table.
        for child_name, child in tables.items():
            if child_name in selected or child_name in self.PROTECTED_TABLES:
                continue
            fk_columns = [
                fk.parent
                for fk in child.foreign_keys
                if fk.column.table.name in selected
            ]
            child_count = self._count_fk_references(child, fk_columns)
            if child_count:
                blockers[child_name] = child_count

        return ResetPreviewData(
            tables=tuple(sorted(selected)),
            counts=counts,
            blockers=blockers,
            finance_counts=finance_counts,
        )

    def delete_tables(self, table_names: Iterable[str]) -> dict[str, int]:
        selected = set(table_names)
        selected.difference_update(self.PROTECTED_TABLES)
        deleted: dict[str, int] = {}
        # Reverse SQLAlchemy dependency order: children are deleted before parents.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in selected:
                continue
            result = self._session.execute(delete(table))
            deleted[table.name] = max(int(result.rowcount or 0), 0)
        self._session.flush()
        return deleted
