"""REC-04 UI cannot block startup to request a manual recovery acknowledgement."""
from pathlib import Path
from types import SimpleNamespace

from centermanager.ui.main_window import MainWindow

def _empty_advisory_queue(monkeypatch):
    from centermanager.platform import recovery_review_notices
    monkeypatch.setattr(
        recovery_review_notices, "RecoveryReviewNotices",
        lambda _journal: SimpleNamespace(pending=lambda: []),
    )



def _notice_fake():
    actions = []
    notices = []
    action = SimpleNamespace(
        setText=lambda value: actions.append(("text", value)),
        setVisible=lambda value: actions.append(("visible", value)),
    )
    return SimpleNamespace(
        _recovery_pending_action=action,
        _manual_review_archives=lambda: [],
        statusBar=lambda: SimpleNamespace(showMessage=lambda text, timeout: notices.append((text, timeout))),
    ), actions, notices


def test_non_modal_recovery_pending_shows_count_and_never_acknowledges(monkeypatch):
    _empty_advisory_queue(monkeypatch)
    from centermanager.platform import recovery_case_registry, write_recovery
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: object())
    monkeypatch.setattr(
        recovery_case_registry, "RecoveryCaseRegistry",
        lambda _: SimpleNamespace(pending_cases=lambda: [{"case_id": "a"}, {"case_id": "b"}]),
    )
    fake, actions, notices = _notice_fake()
    MainWindow._show_pending_recovery_cases(fake)
    assert ("visible", True) in actions
    assert any("2 case" in text for _, text in actions if _ == "text")
    assert notices and "Git MAIN" in notices[0][0]


def test_invalid_recovery_notice_remains_non_modal(monkeypatch):
    _empty_advisory_queue(monkeypatch)
    from centermanager.platform import recovery_case_registry, write_recovery
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: object())
    def raises(_):
        raise RuntimeError("corrupt recovery metadata")
    monkeypatch.setattr(recovery_case_registry, "RecoveryCaseRegistry", raises)
    fake, actions, notices = _notice_fake()
    MainWindow._show_pending_recovery_cases(fake)
    assert ("visible", True) in actions
    assert "Không xác minh" in notices[0][0]


def test_no_recovery_cases_hide_non_modal_notice(monkeypatch):
    _empty_advisory_queue(monkeypatch)
    from centermanager.platform import recovery_case_registry, write_recovery
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: object())
    monkeypatch.setattr(recovery_case_registry, "RecoveryCaseRegistry", lambda _: SimpleNamespace(pending_cases=lambda: []))
    fake, actions, notices = _notice_fake()
    MainWindow._show_pending_recovery_cases(fake)
    assert actions == [("visible", False)]
    assert not notices


def test_startup_recovery_reminder_does_not_invoke_modal_exec():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    source = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    method = source.split("def _show_pending_recovery_cases(", 1)[1].split(
        "def _show_recovery_case_history(", 1
    )[0]
    assert "show_pending_recovery_reminder(" not in method
    assert "QTimer.singleShot(" in method  # Post-login, not startup admission
    assert "mark_reviewed(" not in method
    assert "QMessageBox.warning(" not in method
    assert "def _show_pending_review_notices(" in source
    assert 'addButton("Đã kiểm tra"' in source
    assert 'addButton("Để lần sau"' in source


def test_manual_review_backup_shows_notice_without_acknowledgement(monkeypatch):
    _empty_advisory_queue(monkeypatch)
    from centermanager.platform import recovery_case_registry, write_recovery
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: object())
    monkeypatch.setattr(
        recovery_case_registry, "RecoveryCaseRegistry",
        lambda _: SimpleNamespace(pending_cases=lambda: []),
    )
    fake, actions, notices = _notice_fake()
    fake._manual_review_archives = lambda: [Path("backup-1")]
    MainWindow._show_pending_recovery_cases(fake)
    assert ("visible", True) in actions
    assert any("1 backup Recovery" in value for kind, value in actions if kind == "text")
    assert notices


def test_recovery_history_offers_manual_archive_folder_without_reopening_old_db():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    source = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "def _manual_review_archives(self)" in source
    assert "QDesktopServices.openUrl(" in source
    assert "QUrl.fromLocalFile(" in source
    assert "registries.extend(self._retained_recovery_registries())" not in source
