"""Safety regressions for editable teaching-note autosave and dashboard charts."""
from types import SimpleNamespace

from PySide6.QtCore import Qt

from centermanager.ui.session.session_note_widget import SessionNoteWidget
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


def test_note_autosave_after_edit_preserves_legacy_progress_without_duplicate_input(qapp):
    notes = FakeNotes()
    widget = SessionNoteWidget(notes, session_id=10)
    widget._show_form()
    widget.lesson_content_edit.setPlainText("Algorithms")
    assert widget._dirty
    widget._autosave_timer.stop()
    widget._autosave()
    assert len(notes.calls) == 1
    assert notes.calls[0][0] == "create"
    assert notes.calls[0][1]["teaching_progress"] == TeachingProgress.COMPLETED.value
    assert not widget._dirty
    # Existing stored legacy progress must NOT be overwritten on later edits.
    notes.note.teaching_progress = TeachingProgress.EXCEEDED_PLAN.value
    widget._load_note()
    widget.homework_edit.setPlainText("Practice")
    assert widget.flush_pending()
    assert notes.calls[-1][0] == "update"
    assert "teaching_progress" not in notes.calls[-1][1]
    assert notes.note.teaching_progress == TeachingProgress.EXCEEDED_PLAN.value
    assert "Teaching Progress" not in [
        widget.findChild(type(widget.teaching_combo)).objectName()
    ]


def test_autosave_does_not_write_in_historical_readonly_mode(qapp):
    notes = FakeNotes()
    widget = SessionNoteWidget(notes, session_id=7)
    widget._show_form()
    widget.lesson_content_edit.setPlainText("Draft")
    widget.setEnabled(False)
    widget._autosave()
    assert notes.calls == []
    assert widget.flush_pending()
    assert notes.calls == []


def test_failed_autosave_keeps_draft_for_retry_when_write_returns(qapp):
    notes = FakeNotes(fail=True)
    widget = SessionNoteWidget(notes, session_id=11)
    widget._show_form()
    widget.homework_edit.setPlainText("Do not lose this draft")
    widget._autosave_timer.stop()
    widget._autosave()
    assert widget._dirty
    assert "Not saved" in widget.save_status.text()
    assert widget.homework_edit.toPlainText() == "Do not lose this draft"
    assert not widget.flush_pending()
    assert not widget.set_session(12)
    assert widget._session_id == 11
    notes.fail = False
    assert widget.flush_pending()
    assert widget._session_id == 11
    assert not widget._dirty
    assert notes.note.homework == "Do not lose this draft"


def test_editing_existing_note_can_clear_content_with_empty_string(qapp):
    notes = FakeNotes()
    notes.note = SimpleNamespace(
        teaching_progress="COMPLETED", class_atmosphere="GOOD",
        lesson_content="Existing", homework="Homework",
    )
    widget = SessionNoteWidget(notes, session_id=1)
    widget.lesson_content_edit.clear()
    widget.homework_edit.clear()
    assert widget.flush_pending()
    assert notes.calls[-1][1]["lesson_content"] == ""
    assert notes.calls[-1][1]["homework"] == ""


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
