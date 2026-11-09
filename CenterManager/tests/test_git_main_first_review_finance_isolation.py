"""Safety regressions for Git-MAIN-first review-only startup."""
from pathlib import Path
from types import SimpleNamespace

from centermanager.platform.sync.startup_sync import StartupSynchronization


def test_review_only_finance_staging_is_quarantined_and_never_published(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    finance = runtime / "Attachment" / "Finance"
    finance.mkdir(parents=True)
    old = finance / "legacy-unpublished.pdf"
    old.write_bytes(b"old private receipt")
    from centermanager.platform import write_recovery
    fake_journal = SimpleNamespace(root=tmp_path / "runtime.write-recovery")
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: fake_journal)
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._paths = SimpleNamespace(attachment_dir=runtime / "Attachment")
    assert startup._isolate_unpublished_finance_vouchers_for_review()
    assert not finance.exists()
    archived = list((fake_journal.root / "startup-finance").glob("*/legacy-unpublished.pdf"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == b"old private receipt"
    # A new authorized upload may now create a fresh runtime/Finance folder
    # without rediscovering the old unaccepted voucher.
    assert startup._isolate_unpublished_finance_vouchers_for_review()


def test_review_only_finance_symlink_never_enables_write(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    finance = runtime / "Attachment" / "Finance"
    finance.parent.mkdir(parents=True)
    elsewhere = tmp_path / "external"
    elsewhere.mkdir()
    try:
        finance.symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("Symlink privileges unavailable")
    from centermanager.platform import write_recovery
    monkeypatch.setattr(
        write_recovery, "WriteRecoveryJournal",
        lambda: SimpleNamespace(root=tmp_path / "runtime.write-recovery"),
    )
    startup = StartupSynchronization.__new__(StartupSynchronization)
    startup._paths = SimpleNamespace(attachment_dir=runtime / "Attachment")
    assert not startup._isolate_unpublished_finance_vouchers_for_review()
    assert finance.is_symlink()
