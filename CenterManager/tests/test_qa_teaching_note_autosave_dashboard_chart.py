"""Save-on-close Teaching Note safety and Finance Dashboard presentation."""
from types import SimpleNamespace

from centermanager.ui.session.session_note_widget import SessionNoteWidget
from centermanager.ui.session.session_detail_dialog import SessionDetailDialog
from centermanager.models.session_note import TeachingProgress
from centermanager.ui.shared.chart_card import format_compact_amount, ChartWidget
from centermanager.services.finance_dashboard_service import FinanceDashboardService


class FakeNotes:
    def __init__(self, *, fail=False):
        self.note = None
        self.calls = []
        self.fail = fail

    def get_note(self, session_id):
        return self.note

    def create_note(self, **kwargs):
        self.calls.append(("create", kwargs))
        if self.fail:
            raise RuntimeError("WRITE unavailable")
        self.note = SimpleNamespace(
            teaching_progress=kwargs["teaching_progress"],
            class_atmosphere=kwargs["class_atmosphere"],
            lesson_content=kwargs["lesson_content"],
            homework=kwargs["homework"],
        )
        return self.note

    def update_note(self, **kwargs):
        self.calls.append(("update", kwargs))
        if self.fail:
            raise RuntimeError("WRITE unavailable")
        for key in ("class_atmosphere", "lesson_content", "homework"):
            setattr(self.note, key, kwargs[key])
        return self.note


def test_typing_does_not_write_until_explicit_close_save(qapp):
    notes = FakeNotes()
    widget = SessionNoteWidget(notes, session_id=10)
    widget._show_form()
    widget.lesson_content_edit.setPlainText("Algorithms")
    widget.homework_edit.setPlainText("Practice")
    widget.atmosphere_combo.setCurrentIndex(1)
    qapp.processEvents()
    assert widget.has_pending_changes()
    assert notes.calls == []  # No debounce timer or hidden background writes.
    assert not hasattr(widget, "_autosave_timer")
    assert not hasattr(widget, "save_btn")
    assert widget.flush_pending()  # Called ONLY by parent Save & Close.
    assert len(notes.calls) == 1
    assert notes.calls[0][0] == "create"
    assert notes.calls[0][1]["teaching_progress"] == TeachingProgress.COMPLETED.value
    assert not widget.has_pending_changes()
    from PySide6.QtWidgets import QLabel
    assert not any("Teaching Progress" in label.text() for label in widget.findChildren(QLabel))


def test_update_preserves_legacy_progress_and_waits_until_close(qapp):
    notes = FakeNotes()
    notes.note = SimpleNamespace(
        teaching_progress=TeachingProgress.EXCEEDED_PLAN.value,
        class_atmosphere="GOOD", lesson_content="Old", homework="Old homework",
    )
    widget = SessionNoteWidget(notes, session_id=4)
    widget.homework_edit.setPlainText("New homework")
    qapp.processEvents()
    assert not notes.calls
    assert widget.flush_pending()
    assert notes.calls[-1][0] == "update"
    assert "teaching_progress" not in notes.calls[-1][1]
    assert notes.note.teaching_progress == TeachingProgress.EXCEEDED_PLAN.value


def test_readonly_history_close_never_writes(qapp):
    notes = FakeNotes()
    widget = SessionNoteWidget(notes, session_id=7)
    widget._show_form()
    widget.setEnabled(False)
    assert widget.flush_pending()
    assert notes.calls == []
    assert not widget.has_pending_changes()


def test_failed_save_on_close_preserves_draft_and_blocks_switch(qapp):
    notes = FakeNotes(fail=True)
    widget = SessionNoteWidget(notes, session_id=11)
    widget._show_form()
    widget.homework_edit.setPlainText("Do not lose this draft")
    qapp.processEvents()
    assert notes.calls == []
    assert not widget.flush_pending()
    assert widget.has_pending_changes()
    assert "Not saved" in widget.save_status.text()
    assert widget.homework_edit.toPlainText() == "Do not lose this draft"
    assert not widget.set_session(12)
    assert widget._session_id == 11
    notes.fail = False
    assert widget.flush_pending()
    assert not widget.has_pending_changes()
    assert notes.note.homework == "Do not lose this draft"


def test_save_on_close_can_clear_existing_text(qapp):
    notes = FakeNotes()
    notes.note = SimpleNamespace(
        teaching_progress="COMPLETED", class_atmosphere="GOOD",
        lesson_content="Existing", homework="Homework",
    )
    widget = SessionNoteWidget(notes, session_id=1)
    widget.lesson_content_edit.clear()
    widget.homework_edit.clear()
    assert notes.calls == []
    assert widget.flush_pending()
    assert notes.calls[-1][1]["lesson_content"] == ""
    assert notes.calls[-1][1]["homework"] == ""


def test_parent_close_gate_calls_save_only_on_close(qapp, monkeypatch):
    notes = FakeNotes()
    widget = SessionNoteWidget(notes, session_id=33)
    widget._show_form()
    widget.lesson_content_edit.setPlainText("Save on close")
    parent = SimpleNamespace(note_widget=widget)
    assert notes.calls == []
    assert SessionDetailDialog._save_before_closing(parent)
    assert len(notes.calls) == 1


def test_parent_close_gate_rejects_write_failure(qapp, monkeypatch):
    notes = FakeNotes(fail=True)
    widget = SessionNoteWidget(notes, session_id=35)
    widget._show_form()
    widget.homework_edit.setPlainText("Preserve draft")
    parent = SimpleNamespace(note_widget=widget)
    shown = []
    monkeypatch.setattr(
        "centermanager.ui.session.session_detail_dialog.QMessageBox.warning",
        lambda *args: shown.append(args),
    )
    assert not SessionDetailDialog._save_before_closing(parent)
    assert shown
    assert widget.has_pending_changes()
    assert widget.homework_edit.toPlainText() == "Preserve draft"


def test_close_label_reflects_pending_note_and_read_only(qapp):
    notes = FakeNotes()
    widget = SessionNoteWidget(notes, session_id=36)
    widget._show_form()
    class Label:
        def __init__(self):
            self.text = ""
        def setText(self, value):
            self.text = value
    close_btn = Label()
    parent = SimpleNamespace(note_widget=widget, close_btn=close_btn)
    SessionDetailDialog._update_close_label(parent)
    assert close_btn.text == "Close"
    widget.lesson_content_edit.setPlainText("Note saved only when closing")
    SessionDetailDialog._update_close_label(parent)
    assert close_btn.text == "Save & Close"
    assert notes.calls == []
    widget.setEnabled(False)
    SessionDetailDialog._update_close_label(parent)
    assert close_btn.text == "Close"


def test_window_x_attempts_same_save_gate(qapp):
    class Event:
        def __init__(self):
            self.accepted = None
        def accept(self):
            self.accepted = True
        def ignore(self):
            self.accepted = False
    blocked = SimpleNamespace(_save_before_closing=lambda: False)
    e = Event()
    SessionDetailDialog.closeEvent(blocked, e)
    assert e.accepted is False
    allowed = SimpleNamespace(_save_before_closing=lambda: True)
    SessionDetailDialog.closeEvent(allowed, e)
    assert e.accepted is True


def test_dashboard_chart_compact_ticks_do_not_truncate_large_vnd_amounts(qapp):
    assert format_compact_amount(24_968_794) == "25.0M"
    assert format_compact_amount(10_700_000) == "10.7M"
    assert format_compact_amount(525_000) == "525.0K"
    assert format_compact_amount(0) == "0"
    chart = ChartWidget("bar")
    chart.setData([("Bank In", 24_968_794), ("Cash In", 10_700_000)], ["#1976d2"])
    assert "24,968,794 VND" in chart.toolTip()
    assert "10,700,000 VND" in chart.toolTip()


def test_dashboard_cash_and_bank_are_exactly_the_selected_period_receipts():
    comparison = FinanceDashboardService._build_cash_vs_bank(
        {"Bank": 24_968_794, "Cash": 10_700_000},
        {"Bank": 0, "Cash": 0},
    )
    assert sum(bucket["income"] for bucket in comparison.values()) == 35_668_794
    assert sum(bucket["expense"] for bucket in comparison.values()) == 0


def test_dashboard_zero_realized_expense_is_not_silently_treated_as_full_ledger():
    from centermanager.ui.finance_workspace.finance_dashboard_page import (
        FinanceDashboardPage,
    )
    observed = FinanceDashboardPage._dashboard_scope_text({
        "period_configured": True,
        "revenue_period": 35_668_794,
        "expense_period": 0,
    })
    assert "Paid/Completed" in observed
    assert "Check the Expense page for Pending" in observed
    assert "ALL Enrollment wallets" in observed
    no_period = FinanceDashboardPage._dashboard_scope_text({
        "period_configured": False, "revenue_period": 0, "expense_period": 0,
    })
    assert "Check the Expense page" not in no_period
