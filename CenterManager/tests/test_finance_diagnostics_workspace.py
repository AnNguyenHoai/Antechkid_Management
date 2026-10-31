"""Phase 1 UI and boundary tests against synthetic, never production, finance rows."""
import csv
import io
from time import perf_counter
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace

from sqlalchemy import event, insert, select

from centermanager.core.current_user import CurrentUserContext
from centermanager.dto.finance_diagnostics_dto import FinanceFindingsPage, FinanceFindingsExport
from centermanager.models import Income
from centermanager.services.finance_diagnostics_service import FinanceDiagnosticsService
from centermanager.ui.finance_workspace.finance_diagnostics_page import FinanceDiagnosticsPage
from centermanager.ui.finance_workspace.finance_workspace_shell import FinanceWorkspaceShell
from tests.test_finance_diagnostics_phase0b import (
    AS_OF, VIEWER, db, _identity, _enrollment, _income,
)
from tests.test_finance_workspace_audit_round2 import (
    _Collaboration, _Dashboard, _FinanceShellExpenseService, _FinanceShellIncomeService,
)
from centermanager.events.event_bus import EventBus


def _wait(qtbot, page):
    qtbot.waitUntil(lambda: not page.data_table.content_stack.currentWidget()
                    is page.data_table.loading_state, timeout=10000)


def test_ui_live_findings_filters_detail_and_server_pages(db, qtbot):
    factory, _ = db
    student_id, class_id = _identity(factory, archived=True)
    enrollment_id = _enrollment(factory, student_id, class_id, status="WITHDRAWN")
    legitimate = _income(factory, student_id, class_id, enrollment_id)
    mismatch = _income(factory, student_id, class_id, enrollment_id=999)
    _income(factory, student_id, class_id, status="VOIDED")
    _income(factory, student_id, class_id, deleted=True)
    with factory.begin() as session:
        session.execute(insert(Income), [{
            "student_id": student_id, "class_id": class_id, "amount": 1000,
            "income_type": "Tuition", "payment_method": "CASH",
            "payment_date": AS_OF, "status": "ACTIVE",
        } for _ in range(250)])

    page = FinanceDiagnosticsPage(FinanceDiagnosticsService(factory))
    qtbot.addWidget(page)
    with CurrentUserContext(VIEWER):
        page.as_of_edit.setDate(AS_OF)
        _wait(qtbot, page)
        assert "Total: 251" in page.summary_label.text()
        assert "D01: 250" in page.summary_label.text()
        assert "D02: 1" in page.summary_label.text()
        assert page.data_table.table.rowCount() == 50
        assert page.data_table.total_rows == 251
        assert page.data_table.table.item(0, 0).text() == "D01 / REVIEW"
        page.data_table.page_requested.emit(6, 50)
        _wait(qtbot, page)
        assert page.data_table.table.rowCount() == 1
        assert page.data_table.table.item(0, 1).text() == str(mismatch)
        page._show_detail(0)
        assert f"Income ID: {mismatch}" in page.detail_label.text()
        assert "Linked Student/Class IDs" in page.detail_label.text()
        assert "Possible false positive" in page.detail_label.text()
        assert "Source:" in page.detail_label.text()

        page.rule_combo.setCurrentIndex(2)  # D02 only
        _wait(qtbot, page)
        assert page.data_table.total_rows == 1
        assert page._findings[0].entity_id == mismatch
        assert page._findings[0].entity_id != legitimate
        page.as_of_edit.setDate(date(2026, 10, 1))
        _wait(qtbot, page)
        assert "Total: 0" in page.summary_label.text()
        assert page.data_table.content_stack.currentWidget() is page.data_table.empty_state


def test_ui_backend_failure_is_error_and_unauthorized_read_is_denied(db, qtbot):
    factory, _ = db

    class BrokenService(FinanceDiagnosticsService):
        def get_findings(self, **kwargs):
            return FinanceFindingsPage(
                "ERROR", kwargs["as_of_date"], datetime.now(timezone.utc), "v1", 1, 50,
                None, {}, (), "DIAGNOSTICS_READ_FAILED",
            )

    page = FinanceDiagnosticsPage(BrokenService(factory))
    qtbot.addWidget(page)
    with CurrentUserContext(VIEWER):
        page.refresh()
        qtbot.waitUntil(lambda: "backend ERROR" in page.metadata_label.text(), timeout=10000)
    assert page.data_table.content_stack.currentWidget() is page.data_table.error_state
    assert "Total: —" in page.summary_label.text()

    real = FinanceDiagnosticsPage(FinanceDiagnosticsService(factory))
    qtbot.addWidget(real)
    real.refresh()  # No current user: service boundary must reject it.
    qtbot.waitUntil(lambda: "backend ERROR" in real.metadata_label.text(), timeout=10000)
    assert real.data_table.content_stack.currentWidget() is real.data_table.error_state


def test_ui_export_bom_formula_safety_and_limit_without_partial_file(db, qtbot, tmp_path, monkeypatch):
    factory, _ = db
    student_id, class_id = _identity(factory)
    _income(factory, student_id, class_id)
    service = FinanceDiagnosticsService(factory)
    page = FinanceDiagnosticsPage(service)
    qtbot.addWidget(page)
    target = tmp_path / "findings.csv"
    monkeypatch.setattr(
        "centermanager.ui.finance_workspace.finance_diagnostics_page.QFileDialog.getSaveFileName",
        lambda *_: (str(target), "CSV files (*.csv)"),
    )
    original = service._finding
    monkeypatch.setattr(FinanceDiagnosticsService, "_finding", staticmethod(
        lambda rule, row, as_of, detected: replace(
            original(rule, row, as_of, detected), evidence="=HYPERLINK(\"bad\")",
        )
    ))
    with CurrentUserContext(VIEWER):
        page._choose_export()
        qtbot.waitUntil(lambda: "Export success" in page.export_status.text(), timeout=10000)
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8-sig"))))[0][
        "evidence"
    ].startswith("'=HYPERLINK")

    target.unlink()

    class LimitedService:
        def export_findings_csv(self, **kwargs):
            return FinanceFindingsExport(
                "LIMIT_EXCEEDED", kwargs["as_of_date"], datetime.now(timezone.utc), "v1",
                10001, {"D01": 10001}, None, "EXPORT_ROW_LIMIT_EXCEEDED",
            )

    page._service = LimitedService()
    with CurrentUserContext(VIEWER):
        page._choose_export()
        qtbot.waitUntil(lambda: "LIMIT_EXCEEDED" in page.export_status.text(), timeout=10000)
    assert not target.exists()


def test_export_real_10000_boundary_and_no_finance_mutation(db):
    factory, engine = db
    student_id, class_id = _identity(factory)
    values = {
        "student_id": student_id, "class_id": class_id, "amount": 1000,
        "income_type": "Tuition", "payment_method": "CASH",
        "payment_date": AS_OF, "status": "ACTIVE",
    }
    with factory.begin() as session:
        session.execute(insert(Income), [values.copy() for _ in range(10000)])
    service = FinanceDiagnosticsService(factory)
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    start = perf_counter()
    try:
        with CurrentUserContext(VIEWER):
            accepted = service.export_findings_csv(as_of_date=AS_OF)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    print(f"10,000-finding export: {(perf_counter() - start)*1000:.1f} ms, {len(statements)} SQL calls")
    assert accepted.state == "OK" and accepted.total_count == 10000
    assert len(list(csv.DictReader(io.StringIO(accepted.csv_text)))) == 10000
    assert len(statements) <= 105  # 2 counts, 100 bounded pages, query_only toggles.
    assert sum("LIMIT" in statement.upper() for statement in statements) == 100
    assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                   for statement in statements)
    with factory.begin() as session:
        session.execute(insert(Income), [values])
    with CurrentUserContext(VIEWER):
        rejected = service.export_findings_csv(as_of_date=AS_OF)
    assert rejected.state == "LIMIT_EXCEEDED" and rejected.csv_text is None
    with factory() as session:
        assert session.scalar(select(Income).where(Income.status == "ACTIVE").limit(1)).amount == 1000
        assert session.query(Income).count() == 10001


def test_finance_navigation_gates_diagnostics_route(db, qtbot, monkeypatch):
    factory, _ = db
    user = SimpleNamespace(
        role=VIEWER.role, permissions=VIEWER.permissions, is_active=True,
        is_admin=False, has_permission=lambda name: name == "finance.view",
    )
    with CurrentUserContext(user):
        # Keep the unrelated Dashboard stub from loading while constructing
        # an authorized shell; restore normal routing for the navigation click.
        with monkeypatch.context() as patch:
            patch.setattr(FinanceWorkspaceShell, "_refresh_page", lambda *_: None)
            shell = FinanceWorkspaceShell(
                income_service=_FinanceShellIncomeService(), student_service=object(),
                class_service=object(), expense_service=_FinanceShellExpenseService(),
                dashboard_service=_Dashboard(), outstanding_service=object(),
                collaboration_manager=_Collaboration(EventBus()),
                diagnostics_service=FinanceDiagnosticsService(factory),
            )
        qtbot.addWidget(shell)
        button = next(b for b in shell.nav._buttons if b._page_id == "diagnostics")
        assert button.isEnabled()
        button.click()
        assert shell.content_stack.currentWidget() is shell.diagnostics_page
        assert button.isChecked()
        _wait(qtbot, shell.diagnostics_page)
    shell.navigate_to("income")  # Revoked session cannot leave through a finance route.
    assert shell.content_stack.currentWidget() is shell.diagnostics_page
