from pathlib import Path

from centermanager.dto.outstanding_dto import OutstandingDTO
from centermanager.services.outstanding_service import OutstandingService


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"
PAGE = ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "outstanding_list_page.py"
REPO = ROOT / "src" / "centermanager" / "repositories" / "enrollment_repository.py"
INCOME_REPO = ROOT / "src" / "centermanager" / "repositories" / "income_repository.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_outstanding_status_filter_happens_before_pagination():
    source = _source(SERVICE)
    assert source.index("if status_filter and status_filter not in (dto.status, dto.balance_state)") < source.index(
        "start = max(0, offset)"
    )
    assert "return page_rows, total, stats" in source


def test_outstanding_bulk_reuses_one_service_session_and_exact_enrollment_identity():
    source = _source(SERVICE)
    collect_start = source.index("def _collect_outstanding")
    collect_end = source.index("@staticmethod\n    def _stats_for_rows", collect_start)
    collect_source = source[collect_start:collect_end]
    assert "get_outstanding_for_enrollment(" not in collect_source
    assert "self._calculate_from_enrollment(" in collect_source
    assert "seen_enrollment_ids = set()" in collect_source
    assert "limit=None" in collect_source


def test_outstanding_live_money_uses_enrollment_attributed_active_tuition():
    service_source = _source(SERVICE)
    income_source = _source(INCOME_REPO)
    assert "sum_active_tuition_for_enrollment" in service_source
    assert "as_of_date=as_of_date" in service_source
    assert 'Income.status == Income.STATUS_ACTIVE' in income_source
    assert 'Income.income_type == "Tuition"' in income_source
    assert "Income.enrollment_id == enrollment_id" in income_source
    assert "finance_period_start=" not in service_source


def test_outstanding_repository_can_load_full_period_read_model():
    source = _source(REPO)
    assert "limit: Optional[int] = 100" in source
    assert "joinedload(Enrollment.student)" in source
    assert "joinedload(Enrollment.class_)" in source
    assert "if limit is not None:" in source


def test_outstanding_workspace_uses_real_server_pagination():
    source = _source(PAGE)
    assert "page_requested.connect(self._on_page_requested)" in source
    assert "self.data_table.set_server_data(" in source
    assert "offset=(self._current_page - 1) * self._page_size" in source
    assert "limit=self._page_size" in source
    assert "limit=1000" not in source


def test_outstanding_workspace_preserves_shared_finance_period_contract():
    source = _source(PAGE)
    assert "period_start=self._period_start" in source
    assert "on_date=self._target_date" in source
    assert "month_combo" not in source
    assert "year_combo" not in source


def test_outstanding_workspace_has_filter_kpis_export_and_is_read_only():
    source = _source(PAGE)
    assert "self.class_combo" in source
    assert "self.status_combo" in source
    assert "def _update_kpis" in source
    assert "self.prepaid_kpi" in source
    assert "def _export_csv" in source
    assert "export_outstanding_csv(" in source
    assert "create_income(" not in source
    assert "update_income(" not in source
    assert "delete_income(" not in source
    assert "void_income(" not in source


def test_outstanding_kpis_cover_full_filtered_rows_without_netting_credit():
    rows = [
        OutstandingDTO.create(
            student_id=1,
            student_name="A",
            student_code="A01",
            class_id=10,
            class_name="C1",
            expected_tuition=100,
            paid=40,
        ),
        OutstandingDTO.create(
            student_id=2,
            student_name="B",
            student_code="B01",
            class_id=10,
            class_name="C1",
            expected_tuition=100,
            paid=140,
        ),
        OutstandingDTO.create(
            student_id=3,
            student_name="C",
            student_code="C01",
            class_id=11,
            class_name="C2",
            expected_tuition=0,
            paid=20,
            tuition_configured=False,
        ),
    ]

    stats = OutstandingService._stats_for_rows(rows)

    assert stats["total_rows"] == 3
    assert stats["total_expected"] == 200
    assert stats["total_paid"] == 200
    assert stats["total_outstanding"] == 60
    assert stats["total_prepaid"] == 40
    assert stats["total_students_with_debt"] == 1
    assert stats["total_students_with_prepaid"] == 1
    assert stats["total_unconfigured_tuition"] == 1


def test_outstanding_csv_exports_all_matching_rows_contract():
    source = _source(SERVICE)
    assert "def export_outstanding_csv" in source
    export_start = source.index("def export_outstanding_csv")
    export_source = source[export_start:]
    assert "limit=None" in export_source
    assert '"Prepaid Credit"' in export_source
    assert '"Balance State"' in export_source
    assert '"Finance Period Start"' in export_source
    assert '"Finance Period End"' in export_source
