from types import SimpleNamespace

import centermanager.ui.main_window as main_window_module


class _ButtonStub:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = enabled


class _TopBarStub:
    def __init__(self):
        self.started = []
        self.finished = []
        self.transaction_text = []

    def begin_operation(self, operation_id, message):
        self.started.append((operation_id, message))
        return True

    def finish_operation(self, operation_id):
        self.finished.append(operation_id)
        return True

    def set_transaction_text(self, text):
        self.transaction_text.append(text)


def test_editing_busy_operation_disables_actions_and_restores_ui(monkeypatch):
    cursor_calls = []
    process_events_calls = []
    refresh_calls = []

    monkeypatch.setattr(
        main_window_module.QApplication,
        "setOverrideCursor",
        lambda cursor: cursor_calls.append(("set", cursor)),
    )
    monkeypatch.setattr(
        main_window_module.QApplication,
        "restoreOverrideCursor",
        lambda: cursor_calls.append(("restore", None)),
    )
    monkeypatch.setattr(
        main_window_module.QApplication,
        "processEvents",
        lambda: process_events_calls.append(True),
    )

    top_bar = _TopBarStub()
    window = SimpleNamespace(
        _editing_busy=False,
        app_top_bar=top_bar,
        start_edit_btn=_ButtonStub(),
        finish_edit_btn=_ButtonStub(),
        cancel_btn=_ButtonStub(),
        _update_write_buttons=lambda: refresh_calls.append(True),
    )

    started = main_window_module.MainWindow._begin_editing_operation(
        window,
        "start-editing",
        "Starting editing...",
    )

    assert started is True
    assert window._editing_busy is True
    assert top_bar.started == [("start-editing", "Starting editing...")]
    assert top_bar.transaction_text[-1] == "Starting editing..."
    assert window.start_edit_btn.enabled is False
    assert window.finish_edit_btn.enabled is False
    assert window.cancel_btn.enabled is False
    assert len(process_events_calls) == 1

    # A second click while the synchronous transaction is painting/loading must
    # not start another operation or re-enter write acquisition.
    assert (
        main_window_module.MainWindow._begin_editing_operation(
            window,
            "start-editing",
            "Starting editing...",
        )
        is False
    )
    assert top_bar.started == [("start-editing", "Starting editing...")]

    main_window_module.MainWindow._end_editing_operation(window, "start-editing")

    assert window._editing_busy is False
    assert top_bar.finished == ["start-editing"]
    assert cursor_calls[0][0] == "set"
    assert cursor_calls[-1][0] == "restore"
    assert refresh_calls == [True]


def test_start_and_finish_handlers_ignore_duplicate_clicks_while_busy():
    class _TransactionStub:
        @property
        def state(self):
            raise AssertionError("busy handler must return before reading transaction state")

        @property
        def is_editing(self):
            raise AssertionError("busy handler must return before reading editing state")

    window = SimpleNamespace(_editing_busy=True, _transaction=_TransactionStub())

    main_window_module.MainWindow._on_start_editing(window)
    main_window_module.MainWindow._on_finish_editing(window)
