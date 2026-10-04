from types import SimpleNamespace

import centermanager.ui.application_shell as shell_module


class _ButtonStub:
    def __init__(self, text=""):
        self.enabled = True
        self._text = text

    def setEnabled(self, enabled):
        self.enabled = enabled

    def text(self):
        return self._text


class _SignalStub:
    def __init__(self, callback=None):
        self.callback = callback
        self.emits = 0

    def emit(self):
        self.emits += 1
        if self.callback is not None:
            self.callback()


def test_edit_operation_paints_busy_state_and_blocks_reentry(monkeypatch):
    cursor_calls = []
    process_events_calls = []
    started = []
    finished = []
    transaction_text = []
    reentry_results = []

    monkeypatch.setattr(
        shell_module.QApplication,
        "setOverrideCursor",
        lambda *args: cursor_calls.append(("set", args[-1] if args else None)),
    )
    monkeypatch.setattr(
        shell_module.QApplication,
        "restoreOverrideCursor",
        lambda *args: cursor_calls.append(("restore", None)),
    )
    monkeypatch.setattr(
        shell_module.QApplication,
        "processEvents",
        lambda *args: process_events_calls.append(True),
    )

    # Legacy feedback-operation hooks remain present for real notifications, but
    # routine Start/Finish Editing busy state is now owned by the fixed header.
    top_bar = SimpleNamespace(
        _editing_operation_id=None,
        start_edit_button=_ButtonStub("Start editing"),
        finish_edit_button=_ButtonStub("Finish editing"),
        cancel_edit_button=_ButtonStub("Cancel request"),
        begin_operation=lambda operation_id, message: started.append(
            (operation_id, message)
        ),
        finish_operation=lambda operation_id: finished.append(operation_id),
        set_transaction_text=lambda text: transaction_text.append(text),
    )

    signal = _SignalStub(
        callback=lambda: reentry_results.append(
            shell_module.ApplicationTopBar._run_edit_operation(
                top_bar,
                "start-editing",
                "Starting editing…",
                _SignalStub(),
            )
        )
    )

    result = shell_module.ApplicationTopBar._run_edit_operation(
        top_bar,
        "start-editing",
        "Starting editing…",
        signal,
    )

    assert result is True
    assert signal.emits == 1
    assert reentry_results == [False]
    # PR-C deliberately removed routine edit operations from FeedbackHost.
    assert started == []
    assert finished == []
    assert transaction_text == ["Starting editing…"]
    assert len(process_events_calls) == 1
    assert cursor_calls[0][0] == "set"
    assert cursor_calls[-1][0] == "restore"
    assert top_bar._editing_operation_id is None
    assert top_bar.start_edit_button.enabled is True
    assert top_bar.finish_edit_button.enabled is True
    assert top_bar.cancel_edit_button.enabled is True


def test_waiting_start_button_remains_disabled_after_busy_operation(monkeypatch):
    monkeypatch.setattr(shell_module.QApplication, "setOverrideCursor", lambda *args: None)
    monkeypatch.setattr(shell_module.QApplication, "restoreOverrideCursor", lambda *args: None)
    monkeypatch.setattr(shell_module.QApplication, "processEvents", lambda *args: None)

    start_button = _ButtonStub("Start editing")
    top_bar = SimpleNamespace(
        _editing_operation_id=None,
        start_edit_button=start_button,
        finish_edit_button=_ButtonStub("Finish editing"),
        cancel_edit_button=_ButtonStub("Cancel request"),
        begin_operation=lambda operation_id, message: True,
        finish_operation=lambda operation_id: True,
        set_transaction_text=lambda text: None,
    )

    def project_waiting_state():
        start_button._text = "Waiting..."
        start_button.setEnabled(False)

    shell_module.ApplicationTopBar._run_edit_operation(
        top_bar,
        "start-editing",
        "Starting editing…",
        _SignalStub(project_waiting_state),
    )

    assert start_button.enabled is False
