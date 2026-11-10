"""Git MAIN first: advisory Recovery reminder never authorizes WRITE or blocks login."""
import json
from pathlib import Path
from types import SimpleNamespace

from centermanager.platform.recovery_review_notices import RecoveryReviewNotices


def _journal(tmp_path):
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    file = root / "journal.json"
    file.write_text('{"status":"OPEN","session_id":"prior-write"}', encoding="utf-8")
    return SimpleNamespace(
        root=root, journal=file, runtime=tmp_path / "runtime"
    )


def test_pending_skip_review_and_no_repeat_on_restart(tmp_path):
    journal = _journal(tmp_path)
    events = RecoveryReviewNotices(journal)
    notice_path = events.record(observed_main_oid="a" * 40)
    assert len(events.pending()) == 1
    raw = journal.journal.read_bytes()
    saved = events.validate_notice(notice_path)
    assert (events.root / saved["journal_file"]).read_bytes() == raw

    # A skip/close writes nothing. Another startup must show the same case.
    assert len(RecoveryReviewNotices(journal).pending()) == 1
    assert events.record(observed_main_oid="a" * 40) == notice_path
    assert len(events.pending()) == 1

    # Only explicit acknowledgement suppresses future prompts for this ID.
    events.acknowledge(saved["id"])
    assert events.pending() == []
    assert events.has_recorded_notices()  # Legacy RV-03 popup must not reappear.
    assert events.validate_notice(notice_path)["status"] == "ACKNOWLEDGED"
    assert (events.root / saved["journal_file"]).read_bytes() == raw
    events.record(observed_main_oid="b" * 40)  # unrelated MAIN advance
    assert events.pending() == []


def test_distinct_incidents_are_not_hidden_by_an_old_acknowledgement(tmp_path):
    journal = _journal(tmp_path)
    events = RecoveryReviewNotices(journal)
    earlier = events.record(observed_main_oid="a" * 40)
    events.acknowledge(earlier.stem)
    journal.journal.write_text('{"status":"OPEN","session_id":"second-write"}', encoding="utf-8")
    later = events.record(observed_main_oid="b" * 40)
    assert later != earlier
    assert [x["id"] for x in events.pending()] == [later.stem]


def test_invalid_or_tampered_notice_never_becomes_acknowledged(tmp_path):
    journal = _journal(tmp_path)
    events = RecoveryReviewNotices(journal)
    path = events.record(observed_main_oid="a" * 40)
    data = events.validate_notice(path)
    (events.root / data["journal_file"]).write_bytes(b"modified log")
    assert events.pending() == []
    import pytest
    with pytest.raises(ValueError):
        events.acknowledge(data["id"])
    # Recoverability is never inferred from an invalid log; the original
    # local journal remains physically present and untouched.
    assert journal.journal.is_file()


def test_review_notice_records_no_business_payload_or_remote_credentials(tmp_path):
    journal = _journal(tmp_path)
    events = RecoveryReviewNotices(journal)
    path = events.record(observed_main_oid="a" * 40)
    notice = json.loads(path.read_text(encoding="utf-8"))
    assert "amount" not in notice
    assert "token" not in notice
    assert notice["status"] == "PENDING_REVIEW"
    assert Path(notice["log_directory"]) == journal.root
