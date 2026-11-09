"""Strict, idempotent calendar generation for newly-created monthly classes.

All calendar dates are original scheduled dates. The chosen weekly weekdays are
frozen per class so a plan's immutable month snapshot cannot be repriced later.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Callable

from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.repositories.provider import (
    RepositoryProvider, create_default_repository_provider,
)
from centermanager.models.session import Session, SessionStatus
from centermanager.services.recovery_change_outbox import (
    record_for_active_write, mirror_after_successful_commit,
)


class MonthlyClassScheduleError(ValueError):
    pass


def month_dates(start: date, end: date | None, month: date, weekdays: tuple[int, ...]) -> tuple[date, ...]:
    if type(month) is not date or month.day != 1:
        raise MonthlyClassScheduleError("Month must start on day 1.")
    if not weekdays or len(set(weekdays)) != len(weekdays) or any(
        type(day) is not int or not 0 <= day <= 6 for day in weekdays
    ):
        raise MonthlyClassScheduleError("Choose unique weekdays (Mon=0 ... Sun=6).")
    if end is not None and end < start:
        raise MonthlyClassScheduleError("Invalid class date range.")
    return tuple(
        candidate for n in range(1, monthrange(month.year, month.month)[1] + 1)
        if (candidate := date(month.year, month.month, n)) >= start
        and (end is None or candidate <= end) and candidate.weekday() in weekdays
    )


class MonthlyClassScheduleService:
    def __init__(
        self, session_factory: Callable,
        repository_provider: RepositoryProvider | None = None,
    ):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    def settings(self, class_id: int):
        """Read-only month planner UI contract; old classes have no policy."""
        with self._session_factory() as db:
            repo = self._repository_provider.monthly_tuition(db)
            klass = repo.class_record(class_id)
            policy = repo.class_default(class_id)
            if klass is None or policy is None:
                return None
            selected = tuple(int(day) for day in policy.weekly_days.split(",")) if policy.weekly_days else ()
            return {
                "monthly_fee_vnd": policy.monthly_fee_vnd,
                "effective_month": policy.effective_month,
                "weekly_days": selected,
                "sessions_per_week": klass.sessions_per_week,
                "start_date": klass.start_date,
            }

    @require_permission("lesson.create")
    def create_month_sessions(self, class_id: int, month: date, weekdays: tuple[int, ...]) -> int:
        if type(class_id) is not int or class_id <= 0:
            raise MonthlyClassScheduleError("Invalid class.")
        weekdays = tuple(sorted(weekdays))
        if len(weekdays) > 7:
            raise MonthlyClassScheduleError("At most seven distinct days per week.")
        with self._session_factory() as db:
            repo = self._repository_provider.monthly_tuition(db)
            klass = repo.class_record(class_id)
            policy = repo.class_default(class_id)
            if (klass is None or policy is None or klass.deleted_at is not None
                    or klass.status != "ACTIVE"):
                raise MonthlyClassScheduleError("Only active monthly classes can generate sessions.")
            if type(klass.sessions_per_week) is not int or len(weekdays) != klass.sessions_per_week:
                raise MonthlyClassScheduleError("Selected weekdays must match Sessions / Week.")
            if month < policy.effective_month:
                raise MonthlyClassScheduleError("Cannot generate sessions before monthly billing begins.")
            selected = ",".join(str(day) for day in weekdays)
            if policy.weekly_days is not None and policy.weekly_days != selected:
                raise MonthlyClassScheduleError(
                    "Class weekdays are already fixed; explicit timetable migration required."
                )
            plans = [
                p for p in repo.plans_for_month(class_id, month)
                if p.status in ("ACTIVE", "CLOSED")
            ]
            if plans:
                raise MonthlyClassScheduleError("Monthly plan already activated. Timetable is frozen.")
            if klass.start_date is None:
                raise MonthlyClassScheduleError("Class start date is required.")
            expected_dates = month_dates(klass.start_date, klass.end_date, month, weekdays)
            if not expected_dates:
                raise MonthlyClassScheduleError("No teaching dates for this class/month.")
            # Legacy contract snapshots use a finite max Session number. Do not
            # silently create more teaching sessions than that upper bound.
            # A MONTHLY class may edit its planned upper bound before enrolling.
            if klass.end_date is not None:
                total = sum(
                    1 for offset in range((klass.end_date - klass.start_date).days + 1)
                    if (klass.start_date.fromordinal(klass.start_date.toordinal() + offset).weekday()
                        in weekdays)
                )
                if klass.planned_sessions is None or klass.planned_sessions < total:
                    raise MonthlyClassScheduleError(
                        f"Class Planned Sessions must cover at least {total} calendar lessons "
                        "for the selected teaching weekdays. Update the class first."
                    )
            existing = repo.sessions_for_class(class_id)
            in_month = [row for row in existing if row.scheduled_date.replace(day=1) == month]
            if not in_month and any(row.scheduled_date.replace(day=1) > month for row in existing):
                raise MonthlyClassScheduleError(
                    "Generate earlier missing months first, to keep session numbers chronological."
                )
            if in_month:
                dates = tuple(sorted(row.scheduled_date for row in in_month))
                if dates == expected_dates and policy.weekly_days == selected:
                    return len(in_month)  # repeat click is read-only
                raise MonthlyClassScheduleError(
                    "Month already has teaching sessions; review/remove conflicting draft "
                    "sessions before automatic generation."
                )
            actor = get_current_user()
            if not getattr(actor, "username", None):
                raise MonthlyClassScheduleError("Authenticated actor required.")
            highest = max((row.session_number for row in existing), default=0)
            policy.weekly_days = selected
            new_sessions = [
                Session(
                    class_id=class_id, session_number=highest + offset,
                    title=f"Buổi {highest + offset}",
                    scheduled_date=scheduled, status=SessionStatus.SCHEDULED.value,
                )
                for offset, scheduled in enumerate(expected_dates, start=1)
            ]
            repo.add_month_sessions(new_sessions)
            record_for_active_write(
                db, module="tuition", action="GENERATE_MONTHLY_SESSIONS",
                entity_type="Class", entity_id=class_id,
                summary_args={"class_id": class_id, "month": month.isoformat(), "count": len(expected_dates)},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return len(expected_dates)
