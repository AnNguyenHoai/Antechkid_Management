from __future__ import annotations
from datetime import date, time, timedelta

from centermanager.models.employee_schedule import (
    EmployeeScheduleRule,
    EmployeeScheduleException,
    EmployeeScheduleWeek,
    EmployeeScheduleAssignment,
    VALID_EXCEPTION_TYPES,
)
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.core.current_user import get_current_user
from centermanager.core.clock import get_clock
from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy
from centermanager.services.audit_service import AuditService


class EmployeeScheduleError(Exception):
    pass


class EmployeeScheduleAccessDeniedError(EmployeeScheduleError):
    pass


class EmployeeScheduleValidationError(EmployeeScheduleError):
    pass


class EmployeeScheduleService:
    """Schedule Template + versioned weekly operational schedule boundary."""

    VIEW_SELF = "schedule.view.self"
    VIEW_ALL = "schedule.view.all"
    MANAGE = "schedule.manage"

    AUDIT_MODULE = "employee_weekly_schedule"
    AUDIT_PUBLISHED = "WEEKLY_SCHEDULE_PUBLISHED"
    AUDIT_FROZEN = "WEEKLY_SCHEDULE_FROZEN"
    AUDIT_REOPENED = "WEEKLY_SCHEDULE_REOPENED_FOR_OVERRIDE"

    def __init__(self, session_factory, repository_provider: RepositoryProvider | None = None):
        self._sf = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._audit_service = AuditService(
            session_factory, repository_provider=self._repository_provider
        )

    @staticmethod
    def _user(user=None):
        user = user or get_current_user()
        if user is None:
            raise EmployeeScheduleAccessDeniedError("Authentication is required.")
        return user

    @staticmethod
    def _has(user, capability):
        return EmployeeCapabilityPolicy.has(user, capability)

    def can_view_all(self, user=None):
        u = self._user(user)
        return self._has(u, self.VIEW_ALL) or self._has(u, self.MANAGE)

    def can_view_self(self, user=None):
        u = self._user(user)
        return self._has(u, self.VIEW_SELF) or self.can_view_all(u)

    def _assert_manage(self, user=None):
        u = self._user(user)
        if not self._has(u, self.MANAGE):
            raise EmployeeScheduleAccessDeniedError(f"Permission '{self.MANAGE}' is required.")
        return u

    def _employee(self, employee_id):
        with self._sf() as s:
            e = self._repository_provider.employees(s).get_by_id(employee_id)
            if not e:
                raise EmployeeScheduleValidationError(f"Employee {employee_id} not found.")
            return e

    def _assert_read_scope(self, employee_id, user=None):
        u = self._user(user)
        e = self._employee(employee_id)
        if self._has(u, self.MANAGE) or self._has(u, self.VIEW_ALL):
            return e
        if e.user_id == u.id and self._has(u, self.VIEW_SELF):
            return e
        raise EmployeeScheduleAccessDeniedError("You can only access your own schedule.")

    def _assert_manage_scope(self, employee_id, user=None):
        u = self._assert_manage(user)
        return self._employee(employee_id)

    @staticmethod
    def week_start(value=None):
        d = value or get_clock().today()
        if not isinstance(d, date):
            raise EmployeeScheduleValidationError("A valid schedule week is required.")
        return d - timedelta(days=d.weekday())

    @classmethod
    def next_week(cls, today=None):
        return cls.week_start(today or get_clock().today()) + timedelta(days=7)

    @staticmethod
    def _validate_rule(day_of_week, start_time, end_time, effective_from, effective_to):
        if day_of_week not in range(7):
            raise EmployeeScheduleValidationError("Day of week must be 0-6 (Monday-Sunday).")
        if not isinstance(start_time, time) or not isinstance(end_time, time) or start_time >= end_time:
            raise EmployeeScheduleValidationError("Schedule start time must be before end time.")
        if effective_to is not None and effective_to < effective_from:
            raise EmployeeScheduleValidationError("Effective end date must be on or after the start date.")

    @staticmethod
    def _date_ranges_overlap(a_from, a_to, b_from, b_to):
        return (a_to is None or b_from <= a_to) and (b_to is None or a_from <= b_to)

    @staticmethod
    def _times_overlap(a_start, a_end, b_start, b_end):
        return a_start < b_end and b_start < a_end

    @staticmethod
    def _minutes(start_time, end_time):
        return (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)

    # ------------------------------------------------------------------
    # Schedule Template
    # ------------------------------------------------------------------
    def list_rules(self, employee_id, user=None):
        self._assert_read_scope(employee_id, user)
        with self._sf() as s:
            return self._repository_provider.employee_schedules(s).list_rules(employee_id)

    def list_exceptions(self, employee_id, user=None):
        self._assert_read_scope(employee_id, user)
        with self._sf() as s:
            return self._repository_provider.employee_schedules(s).list_exceptions(employee_id)

    def add_rule(self, employee_id, day_of_week, start_time, end_time, effective_from, effective_to=None, notes=None, user=None):
        self._assert_manage_scope(employee_id, user)
        self._validate_rule(day_of_week, start_time, end_time, effective_from, effective_to)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            for r in repo.list_rules(employee_id):
                if (
                    r.day_of_week == day_of_week
                    and self._date_ranges_overlap(effective_from, effective_to, r.effective_from, r.effective_to)
                    and self._times_overlap(start_time, end_time, r.start_time, r.end_time)
                ):
                    raise EmployeeScheduleValidationError("Schedule overlaps an existing rule for this employee.")
            r = EmployeeScheduleRule(
                employee_id=employee_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                effective_from=effective_from,
                effective_to=effective_to,
                notes=notes or None,
            )
            repo.add_rule(r)
            s.commit()
            return r

    def update_rule(self, rule_id, *, day_of_week, start_time, end_time, effective_from, effective_to=None, notes=None, user=None):
        u = self._user(user)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            r = repo.get_rule(rule_id)
            if not r:
                raise EmployeeScheduleValidationError(f"Schedule rule {rule_id} not found.")
            self._assert_manage_scope(r.employee_id, u)
            self._validate_rule(day_of_week, start_time, end_time, effective_from, effective_to)
            for other in repo.list_rules(r.employee_id):
                if (
                    other.id != r.id
                    and other.day_of_week == day_of_week
                    and self._date_ranges_overlap(effective_from, effective_to, other.effective_from, other.effective_to)
                    and self._times_overlap(start_time, end_time, other.start_time, other.end_time)
                ):
                    raise EmployeeScheduleValidationError("Schedule overlaps an existing rule for this employee.")
            repo.update_rule(
                r,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                effective_from=effective_from,
                effective_to=effective_to,
                notes=notes,
            )
            s.commit()
            return r

    def delete_rule(self, rule_id, user=None):
        u = self._user(user)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            r = repo.get_rule(rule_id)
            if not r:
                return
            self._assert_manage_scope(r.employee_id, u)
            repo.delete_rule(r)
            s.commit()

    def add_exception(self, employee_id, schedule_date, exception_type, start_time=None, end_time=None, notes=None, user=None):
        self._assert_manage_scope(employee_id, user)
        typ = (exception_type or "").upper()
        if typ not in VALID_EXCEPTION_TYPES:
            raise EmployeeScheduleValidationError("Invalid schedule exception type.")
        if typ == "MODIFIED" and (not start_time or not end_time or start_time >= end_time):
            raise EmployeeScheduleValidationError("MODIFIED exception requires a valid start and end time.")
        if typ != "MODIFIED":
            start_time = end_time = None
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            if any(x.schedule_date == schedule_date for x in repo.list_exceptions(employee_id)):
                raise EmployeeScheduleValidationError("An exception already exists for this date.")
            x = EmployeeScheduleException(
                employee_id=employee_id,
                schedule_date=schedule_date,
                exception_type=typ,
                start_time=start_time,
                end_time=end_time,
                notes=notes or None,
            )
            repo.add_exception(x)
            s.commit()
            return x

    def delete_exception(self, exception_id, user=None):
        u = self._user(user)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            x = repo.get_exception(exception_id)
            if not x:
                return
            self._assert_manage_scope(x.employee_id, u)
            repo.delete_exception(x)
            s.commit()

    @staticmethod
    def _effective_template_blocks(repo, employee_id, work_date):
        exceptions = [x for x in repo.list_exceptions(employee_id) if x.schedule_date == work_date]
        if exceptions:
            x = exceptions[0]
            if x.exception_type in {"OFF", "HOLIDAY", "LEAVE"}:
                return []
            return [(x.start_time, x.end_time)] if x.start_time and x.end_time else []
        dow = work_date.weekday()
        return [
            (r.start_time, r.end_time)
            for r in repo.list_rules(employee_id)
            if r.status == "ACTIVE"
            and r.day_of_week == dow
            and r.effective_from <= work_date
            and (r.effective_to is None or work_date <= r.effective_to)
        ]

    def expected_for_date(self, employee_id, work_date: date, user=None):
        self._assert_read_scope(employee_id, user)
        with self._sf() as s:
            return self._effective_template_blocks(
                self._repository_provider.employee_schedules(s), employee_id, work_date
            )

    # ------------------------------------------------------------------
    # Weekly Schedule Planning + lifecycle
    # ------------------------------------------------------------------
    def _accepted_registration(self, session, employee_id, week_start):
        period = self._repository_provider.employee_work_registration_periods(session).get_by_week_start(week_start)
        if period is None:
            return None
        registration = self._repository_provider.employee_work_registrations(session).get_by_employee_period(
            employee_id, period.id
        )
        if registration is None or registration.status != EmployeeWorkRegistration.STATUS_ACCEPTED:
            return None
        return registration

    @staticmethod
    def _covered_by_availability(blocks, work_date, start_time, end_time):
        return any(
            block.work_date == work_date
            and block.start_time <= start_time
            and end_time <= block.end_time
            for block in blocks
        )

    def _validate_assignment(self, work_date, start_time, end_time, week_start, source):
        ws = self.week_start(week_start)
        if not isinstance(work_date, date) or self.week_start(work_date) != ws:
            raise EmployeeScheduleValidationError(
                "Schedule assignment date must be inside the selected Monday-Sunday week."
            )
        if not isinstance(start_time, time) or not isinstance(end_time, time) or start_time >= end_time:
            raise EmployeeScheduleValidationError("Schedule assignment start time must be before end time.")
        if source not in EmployeeScheduleAssignment.VALID_SOURCES:
            raise EmployeeScheduleValidationError("Invalid weekly schedule assignment source.")
        return ws

    def _ensure_available(self, session, employee_id, week_start, work_date, start_time, end_time):
        registration = self._accepted_registration(session, employee_id, week_start)
        if registration is None:
            raise EmployeeScheduleValidationError(
                "Employee has no accepted work registration for this week."
            )
        if not self._covered_by_availability(registration.blocks, work_date, start_time, end_time):
            raise EmployeeScheduleValidationError(
                "Scheduled time must be inside the employee's accepted availability."
            )
        return registration

    def _ensure_no_assignment_overlap(self, repo, employee_id, week_start, work_date, start_time, end_time, exclude_id=None):
        for assignment in repo.list_employee_week(employee_id, week_start):
            if exclude_id is not None and assignment.id == exclude_id:
                continue
            if (
                assignment.work_date == work_date
                and self._times_overlap(start_time, end_time, assignment.start_time, assignment.end_time)
            ):
                raise EmployeeScheduleValidationError(
                    "Schedule assignment overlaps another assignment for this employee."
                )

    @staticmethod
    def _require_draft(week):
        if week.status != EmployeeScheduleWeek.STATUS_DRAFT:
            raise EmployeeScheduleValidationError(
                "Published or frozen schedules are locked. Re-open the week with an override reason before editing."
            )
        return week

    def _validate_publishable(self, session, repo, week):
        assignments = repo.list_week_assignments(week.week_start)
        if not assignments:
            raise EmployeeScheduleValidationError("Cannot publish an empty weekly schedule.")
        for item in assignments:
            self._validate_assignment(
                item.work_date,
                item.start_time,
                item.end_time,
                week.week_start,
                item.source,
            )
            self._ensure_available(
                session,
                item.employee_id,
                week.week_start,
                item.work_date,
                item.start_time,
                item.end_time,
            )
            self._ensure_no_assignment_overlap(
                repo,
                item.employee_id,
                week.week_start,
                item.work_date,
                item.start_time,
                item.end_time,
                exclude_id=item.id,
            )
        return assignments

    def _audit_week(self, session, action, week, actor, details=None):
        payload = {
            "week_start": week.week_start.isoformat(),
            "week_end": week.week_end.isoformat(),
            "status": week.status,
            "version": week.version,
        }
        if details:
            payload.update(details)
        return self._audit_service.record_in_session(
            session,
            action,
            self.AUDIT_MODULE,
            target_type="EmployeeScheduleWeek",
            target_id=week.id,
            target_name=week.week_start.isoformat(),
            details=payload,
            actor=actor,
        )

    def get_week(self, week_start, user=None):
        u = self._user(user)
        if not (self._has(u, self.VIEW_ALL) or self._has(u, self.MANAGE)):
            raise EmployeeScheduleAccessDeniedError(f"Permission '{self.VIEW_ALL}' is required.")
        ws = self.week_start(week_start)
        with self._sf() as s:
            return self._repository_provider.employee_schedules(s).get_week(ws)

    def list_week(self, week_start, user=None):
        u = self._user(user)
        if not (self._has(u, self.VIEW_ALL) or self._has(u, self.MANAGE)):
            raise EmployeeScheduleAccessDeniedError(f"Permission '{self.VIEW_ALL}' is required.")
        ws = self.week_start(week_start)
        with self._sf() as s:
            return self._repository_provider.employee_schedules(s).list_week_assignments(ws)

    def list_employee_week(self, employee_id, week_start, user=None):
        self._assert_read_scope(employee_id, user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            return self._repository_provider.employee_schedules(s).list_employee_week(employee_id, ws)

    def list_official_employee_week(self, employee_id, week_start, user=None):
        """Return only the published/frozen schedule visible as official to employees."""
        self._assert_read_scope(employee_id, user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = repo.get_week(ws)
            if week is None or not week.is_official:
                return []
            return repo.list_employee_week(employee_id, ws)

    def employee_week_state(self, employee_id, week_start, user=None):
        """Read lifecycle metadata without exposing draft assignments as official schedule."""
        u = self._user(user)
        self._assert_read_scope(employee_id, u)
        ws = self.week_start(week_start)
        privileged = self._has(u, self.VIEW_ALL) or self._has(u, self.MANAGE)
        with self._sf() as s:
            week = self._repository_provider.employee_schedules(s).get_week(ws)
            if week is None:
                return {"status": None, "version": None, "official": False}
            official = week.is_official
            return {
                "status": week.status if privileged or official else "UNPUBLISHED",
                "version": week.version if privileged or official else None,
                "official": official,
                "published_at": week.published_at if official else None,
                "frozen_at": week.frozen_at if week.status == EmployeeScheduleWeek.STATUS_FROZEN else None,
            }

    def add_week_assignment(
        self,
        employee_id,
        work_date,
        start_time,
        end_time,
        *,
        week_start=None,
        source=EmployeeScheduleAssignment.SOURCE_MANUAL,
        note=None,
        user=None,
    ):
        self._assert_manage_scope(employee_id, user)
        ws = self._validate_assignment(work_date, start_time, end_time, week_start or work_date, source)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = self._require_draft(repo.get_or_create_week(ws))
            self._ensure_available(s, employee_id, ws, work_date, start_time, end_time)
            self._ensure_no_assignment_overlap(repo, employee_id, ws, work_date, start_time, end_time)
            assignment = EmployeeScheduleAssignment(
                schedule_week_id=week.id,
                employee_id=employee_id,
                work_date=work_date,
                start_time=start_time,
                end_time=end_time,
                source=source,
                note=(note or "").strip() or None,
            )
            repo.add_assignment(assignment)
            s.commit()
            return assignment

    def delete_week_assignment(self, assignment_id, user=None):
        u = self._user(user)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            assignment = repo.get_assignment(assignment_id)
            if assignment is None:
                return
            self._assert_manage_scope(assignment.employee_id, u)
            self._require_draft(assignment.schedule_week)
            repo.delete_assignment(assignment)
            s.commit()

    def seed_week_from_registration(self, employee_id, week_start, user=None):
        """Copy accepted availability into a DRAFT weekly schedule once."""
        self._assert_manage_scope(employee_id, user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = self._require_draft(repo.get_or_create_week(ws))
            registration = self._accepted_registration(s, employee_id, ws)
            if registration is None:
                raise EmployeeScheduleValidationError("Employee has no accepted work registration for this week.")
            existing = repo.list_employee_week(employee_id, ws)
            created = 0
            for block in registration.blocks:
                if any(
                    item.work_date == block.work_date
                    and self._times_overlap(block.start_time, block.end_time, item.start_time, item.end_time)
                    for item in existing
                ):
                    continue
                assignment = EmployeeScheduleAssignment(
                    schedule_week_id=week.id,
                    employee_id=employee_id,
                    work_date=block.work_date,
                    start_time=block.start_time,
                    end_time=block.end_time,
                    source=EmployeeScheduleAssignment.SOURCE_REGISTRATION,
                    note=block.notes,
                )
                repo.add_assignment(assignment)
                existing.append(assignment)
                created += 1
            s.commit()
            return created

    def seed_week_from_template(self, employee_id, week_start, user=None):
        """Build a DRAFT weekly schedule from template within accepted availability."""
        self._assert_manage_scope(employee_id, user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = self._require_draft(repo.get_or_create_week(ws))
            registration = self._accepted_registration(s, employee_id, ws)
            if registration is None:
                raise EmployeeScheduleValidationError("Employee has no accepted work registration for this week.")
            existing = repo.list_employee_week(employee_id, ws)
            created = 0
            skipped_outside_availability = 0
            for offset in range(7):
                work_date = ws + timedelta(days=offset)
                for start_time, end_time in self._effective_template_blocks(repo, employee_id, work_date):
                    if not self._covered_by_availability(registration.blocks, work_date, start_time, end_time):
                        skipped_outside_availability += 1
                        continue
                    if any(
                        item.work_date == work_date
                        and self._times_overlap(start_time, end_time, item.start_time, item.end_time)
                        for item in existing
                    ):
                        continue
                    assignment = EmployeeScheduleAssignment(
                        schedule_week_id=week.id,
                        employee_id=employee_id,
                        work_date=work_date,
                        start_time=start_time,
                        end_time=end_time,
                        source=EmployeeScheduleAssignment.SOURCE_TEMPLATE,
                    )
                    repo.add_assignment(assignment)
                    existing.append(assignment)
                    created += 1
            s.commit()
            return {"created": created, "skipped_outside_availability": skipped_outside_availability}

    def publish_week(self, week_start, user=None):
        """Publish a validated DRAFT as the official employee schedule."""
        actor = self._assert_manage(user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = repo.get_week(ws)
            if week is None:
                raise EmployeeScheduleValidationError("Weekly schedule draft not found.")
            self._require_draft(week)
            assignments = self._validate_publishable(s, repo, week)
            week.status = EmployeeScheduleWeek.STATUS_PUBLISHED
            week.published_at = get_clock().now()
            week.published_by_user_id = actor.id
            week.frozen_at = None
            week.frozen_by_user_id = None
            self._audit_week(
                s,
                self.AUDIT_PUBLISHED,
                week,
                actor,
                {"assignment_count": len(assignments)},
            )
            s.commit()
            return week

    def freeze_week(self, week_start, user=None):
        """Freeze a published schedule so it remains an immutable official record."""
        actor = self._assert_manage(user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = repo.get_week(ws)
            if week is None or week.status != EmployeeScheduleWeek.STATUS_PUBLISHED:
                raise EmployeeScheduleValidationError("Only a published weekly schedule can be frozen.")
            week.status = EmployeeScheduleWeek.STATUS_FROZEN
            week.frozen_at = get_clock().now()
            week.frozen_by_user_id = actor.id
            self._audit_week(s, self.AUDIT_FROZEN, week, actor)
            s.commit()
            return week

    def reopen_week_for_override(self, week_start, reason, user=None):
        """Re-open PUBLISHED/FROZEN schedule as a new DRAFT revision.

        A reason is mandatory because this operation changes an already official
        schedule. The previous lifecycle state remains available in audit logs.
        """
        actor = self._assert_manage(user)
        reason = (reason or "").strip()
        if not reason:
            raise EmployeeScheduleValidationError("An override reason is required.")
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            week = repo.get_week(ws)
            if week is None or week.status not in {
                EmployeeScheduleWeek.STATUS_PUBLISHED,
                EmployeeScheduleWeek.STATUS_FROZEN,
            }:
                raise EmployeeScheduleValidationError(
                    "Only a published or frozen weekly schedule can be re-opened for override."
                )
            old_status = week.status
            old_version = week.version
            week.status = EmployeeScheduleWeek.STATUS_DRAFT
            week.version += 1
            week.published_at = None
            week.published_by_user_id = None
            week.frozen_at = None
            week.frozen_by_user_id = None
            self._audit_week(
                s,
                self.AUDIT_REOPENED,
                week,
                actor,
                {
                    "old_status": old_status,
                    "old_version": old_version,
                    "new_version": week.version,
                    "reason": reason,
                },
            )
            s.commit()
            return week

    def registered_vs_scheduled(self, employee_id, week_start, user=None):
        """Return planning totals for one employee/week in hours."""
        self._assert_read_scope(employee_id, user)
        ws = self.week_start(week_start)
        with self._sf() as s:
            repo = self._repository_provider.employee_schedules(s)
            registration = self._accepted_registration(s, employee_id, ws)
            registered_minutes = sum(
                self._minutes(block.start_time, block.end_time)
                for block in (registration.blocks if registration else [])
            )
            assignments = repo.list_employee_week(employee_id, ws)
            scheduled_minutes = sum(self._minutes(item.start_time, item.end_time) for item in assignments)
            week = repo.get_week(ws)
            return {
                "week_start": ws,
                "week_end": ws + timedelta(days=6),
                "registration_status": registration.status if registration else None,
                "schedule_status": week.status if week else None,
                "schedule_version": week.version if week else None,
                "registered_hours": registered_minutes / 60,
                "scheduled_hours": scheduled_minutes / 60,
                "remaining_hours": (registered_minutes - scheduled_minutes) / 60,
                "assignment_count": len(assignments),
            }
