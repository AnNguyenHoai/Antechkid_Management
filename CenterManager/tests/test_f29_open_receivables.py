"""F-29: old archived/withdrawn tuition debt remains visible across finance periods.

Synthetic enrollment/service fixtures; no production data or remote lock.
"""
import csv
import io
from datetime import date
from decimal import Decimal

from tests.test_tuition_08_outstanding_v2_core import (
    _enrollment, _completed, _service,
)
from centermanager.services.outstanding_service import OutstandingService


def _historical_debt():
    old = _enrollment(101, unit_fee="100000", planned_sessions=2, end_session=2)
    old.start_date = date(2026, 9, 1)
    old.end_date = date(2026, 9, 30)
    old.status = "WITHDRAWN"
    old.student.status = "ARCHIVED"
    old.class_.deleted_at = date(2026, 9, 30)
    sessions = [_completed(20, i, date(2026, 9, i * 5)) for i in (1, 2)]
    service, provider = _service(
        [old], {20: sessions},
        {101: [(date(2026, 9, 20), Decimal("50000"))]},
    )
    original = provider.enrollment_repo.list_for_outstanding

    def period_filter(**kwargs):
        items, _ = original(**kwargs)
        start, end = kwargs.get("period_start"), kwargs.get("period_end")
        items = [
            item for item in items
            if (start is None or item.end_date is None or item.end_date >= start)
            and (end is None or item.start_date is None or item.start_date <= end)
        ]
        return items, len(items)

    provider.enrollment_repo.list_for_outstanding = period_filter
    service._report_period_for_request = lambda *args, **kwargs: (
        date(2026, 10, 1), date(2026, 10, 31), True
    )
    return service, provider, old


def test_archived_class_and_student_debt_carries_forward_to_next_period():
    service, _, old = _historical_debt()
    rows, count, stats = service.get_outstanding_page(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        period_start=date(2026, 10, 1), on_date=date(2026, 10, 31),
        limit=None,
    )
    assert count == 1
    assert rows[0].enrollment_id == old.id
    assert rows[0].outstanding == Decimal("150000.0000")
    assert stats["total_outstanding"] == Decimal("150000.0000")
    assert rows[0].period_start is None
    assert rows[0].period_end is None


def test_period_activity_does_not_change_historical_filtering():
    service, _, _ = _historical_debt()
    rows, total, _ = service.get_outstanding_page(
        view=OutstandingService.VIEW_PERIOD_ACTIVITY,
        period_start=date(2026, 10, 1), on_date=date(2026, 10, 31),
        limit=None,
    )
    assert total == 0
    assert rows == []


def test_open_receivables_as_of_is_consistent_and_does_not_include_future_enrollments():
    service, _, old = _historical_debt()
    old.start_date = date(2026, 11, 1)
    rows, total, _ = service.get_outstanding_page(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        on_date=date(2026, 10, 31), limit=None,
    )
    assert total == 0
    assert rows == []


def test_open_receivables_csv_and_class_filter_reuse_full_view():
    service, _, _ = _historical_debt()
    classes = service.list_outstanding_classes(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        period_start=date(2026, 10, 1), on_date=date(2026, 10, 31)
    )
    assert classes == [(20, "Class 20")]
    output = service.export_outstanding_csv(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        period_start=date(2026, 10, 1), on_date=date(2026, 10, 31)
    )
    data = list(csv.DictReader(io.StringIO(output)))
    assert len(data) == 1
    assert data[0]["Student Code"] == "ST10"
    assert Decimal(data[0]["Outstanding"]) == Decimal("150000")
    assert data[0]["Finance Period Start"] == ""


def test_repaid_old_debt_drops_out_at_as_of_but_is_not_deleted():
    service, provider, _ = _historical_debt()
    provider.income_repo._payments[101].append(
        (date(2026, 11, 5), Decimal("150000"))
    )
    _rows, count, _ = service.get_outstanding_page(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        on_date=date(2026, 10, 31),
    )
    assert count == 1
    _rows, count, _ = service.get_outstanding_page(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        on_date=date(2026, 11, 30),
    )
    assert count == 0


def test_open_receivables_works_without_finance_period_configuration():
    service, _, _ = _historical_debt()
    # An absent FinancePeriod must not hide historical debts in the open view.
    service._report_period_for_request = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Open receivables must not resolve a finance period")
    )
    rows, total, _ = service.get_outstanding_page(
        view=OutstandingService.VIEW_OPEN_RECEIVABLES,
        on_date=date(2026, 10, 31), limit=None,
    )
    assert total == 1
    assert rows[0].balance_state == "OWED"


def test_workspace_defaults_open_receivables_and_passes_view_to_csv():
    from pathlib import Path
    ui = (Path(__file__).resolve().parents[1] / "src" / "centermanager"
          / "ui" / "finance_workspace" / "outstanding_list_page.py").read_text(encoding="utf-8")
    assert 'self.view_combo.addItem("Công nợ còn mở (tất cả kỳ)", OutstandingService.VIEW_OPEN_RECEIVABLES)' in ui
    assert "view=self._view()" in ui
    assert ui.count("view=self._view()") >= 4
