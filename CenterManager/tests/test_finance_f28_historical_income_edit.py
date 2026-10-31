"""F-28: edit historical Income without changing its persisted attribution."""
from datetime import date, datetime
from types import SimpleNamespace
from time import perf_counter

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.models import Class, Enrollment, Income, Student
from centermanager.models.finance_period import FinancePeriod
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.models.audit_log import AuditLog
from centermanager.services.class_service import ClassService
from centermanager.services.income_service import IncomeService, IncomeNotFoundError, IncomeValidationError
from centermanager.services.permission_service import PermissionDeniedError
from centermanager.services.student_service import StudentService
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog


PAYMENT_DATE = date(2026, 10, 20)
EDITOR = SimpleNamespace(
    role=SimpleNamespace(name="MANAGER"),
    permissions={"finance.view", "finance.income.update"},
    full_name="Synthetic Reviewer", is_admin=False,
)


@pytest.fixture
def history(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'f28.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        period = FinancePeriod(effective_from=date(2026, 10, 1), duration_months=1,
                               status="ACTIVE")
        session.add(period)
        session.flush()
        period_id = period.id
    students = StudentService(factory)
    classes = ClassService(factory)
    timeline = SimpleNamespace(log_event=lambda **_: None)
    incomes = IncomeService(factory, students, classes, timeline, None)
    yield factory, students, classes, incomes, period_id
    engine.dispose()


def records(history, *, archived=False, enrollment_status="ACTIVE", student_status=None,
            enrollment_id="create", income_status="ACTIVE", deleted=False,
            missing_student=False, missing_class=False, income_type="Tuition"):
    factory, _, _, _, period_id = history
    with factory.begin() as session:
        suffix = session.scalar(select(func.count(Student.id))) + 1
        student = Student(student_code=f"S{suffix}", full_name="Synthetic Student",
                          status=student_status or ("ARCHIVED" if archived else "ACTIVE"))
        class_ = Class(name=f"Historical Class {suffix}", status="ARCHIVED" if archived else "ACTIVE",
                       deleted_at=datetime(2026, 10, 21) if archived else None)
        other = Class(name=f"Active Other Class {suffix}", status="ACTIVE")
        session.add_all([student, class_, other])
        session.flush()
        enrollment = Enrollment(student_id=student.id, class_id=class_.id,
                                status=enrollment_status, start_date=date(2026, 9, 1),
                                end_date=date(2026, 10, 15))
        session.add(enrollment)
        session.flush()
        identity = (student.id, class_.id, enrollment.id)
        income = Income(student_id=9999 if missing_student else student.id,
                        class_id=9999 if missing_class else class_.id,
                        enrollment_id=(enrollment.id if enrollment_id == "create" else enrollment_id),
                        amount=100000, income_type=income_type,
                        payment_method="CASH", payment_date=PAYMENT_DATE,
                        finance_period_id=period_id,
                        finance_period_start=date(2026, 10, 1),
                        status=income_status, note="original", received_by="System",
                        payment_period="",
                        deleted_at=datetime(2026, 10, 22) if deleted else None)
        session.add(income)
        session.flush()
        return income.id, identity


def open_dialog(history, income_id, qtbot):
    _, students, classes, incomes, _ = history
    with CurrentUserContext(EDITOR):
        dialog = IncomeFormDialog(incomes, students, classes, income_id=income_id)
    qtbot.addWidget(dialog)
    return dialog


def test_archived_class_and_withdrawn_enrollment_are_the_exact_edit_identity(history, qtbot):
    income_id, (student_id, class_id, enrollment_id) = records(
        history, archived=True, enrollment_status="WITHDRAWN"
    )
    dialog = open_dialog(history, income_id, qtbot)
    assert dialog.student_combo.currentData() == student_id
    assert dialog.class_combo.currentData() == class_id
    assert dialog.enrollment_combo.currentData() == enrollment_id
    assert dialog.save_btn.isEnabled()
    assert f"Class #{class_id}" in dialog.identity_label.text()
    assert "WITHDRAWN" in dialog.enrollment_combo.currentText()


@pytest.mark.parametrize("student_status,archived", [("ACTIVE", False), ("ARCHIVED", True)])
def test_active_and_archived_student_preserve_exact_ids(history, qtbot, student_status, archived):
    income_id, identity = records(history, student_status=student_status, archived=archived)
    dialog = open_dialog(history, income_id, qtbot)
    assert tuple(combo.currentData() for combo in (
        dialog.student_combo, dialog.class_combo, dialog.enrollment_combo
    )) == identity
    assert dialog.save_btn.isEnabled()


@pytest.mark.parametrize("missing_student,missing_class,enrollment_id", [
    (True, False, "create"), (False, True, "create"), (False, False, 9999),
])
def test_missing_persisted_reference_is_explicit_and_cannot_save(
    history, qtbot, monkeypatch, missing_student, missing_class, enrollment_id,
):
    income_id, _ = records(history, missing_student=missing_student,
                           missing_class=missing_class, enrollment_id=enrollment_id)
    warnings = []
    monkeypatch.setattr(
        "centermanager.ui.finance_workspace.income_form_dialog.QMessageBox.warning",
        lambda *_args: warnings.append(_args[-1]),
    )
    dialog = open_dialog(history, income_id, qtbot)
    assert "UNRESOLVED" in dialog.identity_label.text()
    assert not dialog.save_btn.isEnabled()
    assert "UNRESOLVED" in (
        dialog.student_combo.currentText() + dialog.class_combo.currentText()
        + dialog.enrollment_combo.currentText()
    )
    dialog._save()  # Even a programmatic click must not bypass the guard.
    assert warnings
    with history[0]() as session:
        assert session.get(Income, income_id).note == "original"
        assert session.query(AuditLog).count() == 0


def test_legacy_null_enrollment_and_multiple_contracts_are_not_auto_attributed(history, qtbot):
    income_id, (student_id, class_id, _) = records(history, enrollment_id=None)
    with history[0].begin() as session:
        session.add(Enrollment(student_id=student_id, class_id=class_id,
                               status="COMPLETED", start_date=date(2026, 1, 1)))
    dialog = open_dialog(history, income_id, qtbot)
    assert dialog.enrollment_combo.currentData() is None
    assert "Legacy" in dialog.enrollment_combo.currentText()
    assert "chưa đối soát" in dialog.identity_label.text()
    assert dialog.save_btn.isEnabled()
    dialog.note_edit.setText("reviewed, still unattributed")
    with CurrentUserContext(EDITOR):
        dialog._save()
    with history[0]() as session:
        income = session.get(Income, income_id)
        assert (income.student_id, income.class_id, income.enrollment_id) == (
            student_id, class_id, None
        )
        assert income.note == "reviewed, still unattributed"


def test_multiple_contracts_selects_original_enrollment_without_guessing(history, qtbot):
    income_id, (student_id, class_id, enrollment_id) = records(history)
    with history[0].begin() as session:
        session.add(Enrollment(student_id=student_id, class_id=class_id,
                               status="WITHDRAWN", start_date=date(2026, 1, 1)))
    dialog = open_dialog(history, income_id, qtbot)
    assert dialog.enrollment_combo.count() >= 3
    assert dialog.enrollment_combo.currentData() == enrollment_id
    assert dialog.save_btn.isEnabled()


def test_unchanged_save_and_note_edit_keep_financial_identity_and_audit(history, qtbot):
    income_id, identity = records(history, archived=True, enrollment_status="WITHDRAWN")
    dialog = open_dialog(history, income_id, qtbot)
    with CurrentUserContext(EDITOR):
        dialog._save()
    with history[0]() as session:
        row = session.get(Income, income_id)
        assert (row.student_id, row.class_id, row.enrollment_id) == identity
        assert row.note == "original"
        assert session.query(AuditLog).count() == 0

    dialog = open_dialog(history, income_id, qtbot)
    dialog.note_edit.setText("historical payment reviewed")
    with CurrentUserContext(EDITOR):
        dialog._save()
    with history[0]() as session:
        row = session.get(Income, income_id)
        assert (row.student_id, row.class_id, row.enrollment_id) == identity
        assert (row.amount, row.payment_method, row.payment_date) == (
            100000, "CASH", PAYMENT_DATE
        )
        assert row.note == "historical payment reviewed"
        logs = session.query(AuditLog).all()
        assert len(logs) == 1 and logs[0].action == "UPDATE"
        assert str(identity[1]) in logs[0].details


def test_voided_deleted_and_closed_period_cannot_be_edited(history, qtbot, monkeypatch):
    voided_id, _ = records(history, income_status="VOIDED")
    dialog = open_dialog(history, voided_id, qtbot)
    assert not dialog.save_btn.isEnabled()
    assert "không ACTIVE" in dialog.identity_label.text()
    with CurrentUserContext(EDITOR), pytest.raises(IncomeValidationError):
        history[3].update_income(voided_id, note="must fail")

    deleted_id, _ = records(history, deleted=True)
    errors = []
    monkeypatch.setattr(
        "centermanager.ui.finance_workspace.income_form_dialog.QMessageBox.critical",
        lambda *_args: errors.append(_args[-1]),
    )
    open_dialog(history, deleted_id, qtbot)
    assert errors
    with CurrentUserContext(EDITOR), pytest.raises(IncomeNotFoundError):
        history[3].update_income(deleted_id, note="must fail")

    active_id, _ = records(history)
    with history[0].begin() as session:
        session.add(FinancialSettlement(
            finance_period_start=date(2026, 10, 1),
            finance_period_end=date(2026, 10, 31), status="CONFIRMED",
        ))
    warnings = []
    monkeypatch.setattr(
        "centermanager.ui.finance_workspace.income_form_dialog.QMessageBox.warning",
        lambda *_args: warnings.append(_args[-1]),
    )
    closed_dialog = open_dialog(history, active_id, qtbot)
    closed_dialog.note_edit.setText("closed")
    with CurrentUserContext(EDITOR):
        closed_dialog._save()
    assert warnings and "closed" in warnings[-1].lower()
    with CurrentUserContext(EDITOR), pytest.raises(IncomeValidationError):
        history[3].update_income(active_id, note="closed")
    with history[0]() as session:
        assert session.get(Income, active_id).note == "original"


def test_unauthorized_editor_cannot_load_or_update(history, qtbot, monkeypatch):
    income_id, _ = records(history)
    errors = []
    monkeypatch.setattr(
        "centermanager.ui.finance_workspace.income_form_dialog.QMessageBox.critical",
        lambda *_args: errors.append(_args[-1]),
    )
    _, students, classes, incomes, _ = history
    with CurrentUserContext(None):
        dialog = IncomeFormDialog(incomes, students, classes, income_id=income_id)
    qtbot.addWidget(dialog)
    assert errors and dialog.result() == dialog.DialogCode.Rejected
    with CurrentUserContext(None), pytest.raises(PermissionDeniedError):
        incomes.update_income(income_id, note="not authorized")

    viewer = SimpleNamespace(role=EDITOR.role, permissions={"finance.view"},
                             full_name="Read only", is_admin=False)
    with CurrentUserContext(viewer):
        dialog = IncomeFormDialog(incomes, students, classes, income_id=income_id)
    qtbot.addWidget(dialog)
    assert dialog.save_btn.isEnabled()  # The list route owns UI capability projection.
    dialog.note_edit.setText("unauthorized")
    previous_errors = len(errors)
    with CurrentUserContext(viewer):
        dialog._save()
    assert len(errors) == previous_errors + 1
    with history[0]() as session:
        assert session.get(Income, income_id).note == "original"


def test_parent_refresh_during_modal_edit_does_not_change_selection(history, qtbot):
    income_id, identity = records(history, archived=True, enrollment_status="WITHDRAWN")
    dialog = open_dialog(history, income_id, qtbot)
    # Rebuild option lists while a modal editor is open, as a concurrent
    # workspace refresh can do. The persisted selection must be restored.
    dialog._load_students()
    dialog._load_classes()
    dialog._reload_enrollments()
    assert tuple(combo.currentData() for combo in (
        dialog.student_combo, dialog.class_combo, dialog.enrollment_combo
    )) == identity
    assert dialog.save_btn.isEnabled()


def test_programmatic_option_drift_fails_closed_before_service_write(history, qtbot, monkeypatch):
    income_id, identity = records(history, archived=True)
    dialog = open_dialog(history, income_id, qtbot)
    other_index = next(i for i in range(dialog.class_combo.count())
                       if dialog.class_combo.itemData(i) != identity[1])
    dialog.class_combo.setCurrentIndex(other_index)  # Simulate a stale option refresh.
    warnings = []
    monkeypatch.setattr(
        "centermanager.ui.finance_workspace.income_form_dialog.QMessageBox.warning",
        lambda *_args: warnings.append(_args[-1]),
    )
    dialog.note_edit.setText("should not commit")
    with CurrentUserContext(EDITOR):
        dialog._save()
    assert warnings
    with history[0]() as session:
        row = session.get(Income, income_id)
        assert (row.student_id, row.class_id, row.enrollment_id) == identity
        assert row.note == "original"


def test_edit_load_adds_only_one_historical_class_not_the_archive_catalog(history, qtbot):
    factory, _, _, _, _ = history
    income_id, _ = records(history, archived=True)
    with factory.begin() as session:
        session.add_all([
            Class(name=f"Old {i}", status="ARCHIVED", deleted_at=datetime(2026, 10, 21))
            for i in range(250)
        ])
    statements = []

    def record(_conn, _cursor, sql, _params, _context, _many):
        statements.append(sql)

    engine = factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", record)
    started = perf_counter()
    try:
        dialog = open_dialog(history, income_id, qtbot)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    elapsed_ms = (perf_counter() - started) * 1000
    print(f"F-28 edit load with 250 unrelated archives: {elapsed_ms:.1f} ms, {len(statements)} SQL calls")
    assert dialog.class_combo.count() == 2  # One active plus exact archived Class.
    assert len(statements) < 30
    assert not any("INSERT " in sql.upper() or "UPDATE " in sql.upper() for sql in statements)
