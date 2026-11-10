"""Readable Recovery export: authenticated events, conservative evidence statements."""
import json
from types import SimpleNamespace

import pytest

from centermanager.platform.recovery_change_mirror import mirror_committed_payload
from centermanager.platform.recovery_review_notices import RecoveryReviewNotices
from centermanager.platform.recovery_readable_report import build_notice_report


def _notice(tmp_path):
    root = tmp_path / "runtime.write-recovery"
    root.mkdir()
    journal = root / "journal.json"
    journal.write_text(json.dumps({"session_id": "write-123", "status": "OPEN"}), encoding="utf-8")
    notices = RecoveryReviewNotices(SimpleNamespace(
        root=root, runtime=tmp_path / "runtime", journal=journal
    ))
    path = notices.record(observed_main_oid="a" * 40)
    return notices, notices.validate_notice(path)


def test_export_authenticated_event_and_unknown_coverage(tmp_path):
    notices, notice = _notice(tmp_path)
    key = bytes(range(32))
    event = {
        "write_session_id": "write-123",
        "event_id": "a3b3c3d3-1111-4111-8111-111111111111",
        "operation_id": "b4b4c4d4-2222-4222-8222-222222222222",
        "module": "finance", "action": "create_income",
        "entity_type": "Income", "entity_id": "125",
        "actor_id": "3", "occurred_at_utc": "2026-11-10T01:00:00",
        "summary_args_json": json.dumps({"student_id": "42", "income_id": "125"}),
    }
    mirror_committed_payload(
        json.dumps(event).encode(), recovery_root=notices.journal.root,
        encryption_key=key,
    )
    report = build_notice_report(notices, notice, encryption_key=key)
    assert "finance / create_income" in report
    assert "student_id: 42" in report
    assert "UNKNOWN" in report
    assert "KHÔNG phải danh sách dữ liệu chắc chắn bị mất" in report
    assert not list(tmp_path.rglob("*.txt"))  # no automatic plaintext file


def test_empty_mirror_never_claims_no_changes(tmp_path):
    notices, notice = _notice(tmp_path)
    report = build_notice_report(notices, notice, encryption_key=bytes(range(32)))
    assert "Không tìm thấy sự kiện" in report
    assert "KHÔNG có nghĩa" in report


def test_invalid_segment_is_counted_not_silently_trusted(tmp_path):
    notices, notice = _notice(tmp_path)
    folder = notices.journal.root / "rv02-committed-events" / "write-123"
    folder.mkdir(parents=True)
    (folder / "a3b3c3d3-1111-4111-8111-111111111111.enc").write_bytes(b"bad")
    report = build_notice_report(notices, notice, encryption_key=bytes(range(32)))
    assert "không đọc/xác minh được: 1" in report
    assert "UNKNOWN" in report


def test_tampered_notice_rejected_before_decryption(tmp_path):
    notices, notice = _notice(tmp_path)
    notice["observed_main_oid"] = "b" * 40
    with pytest.raises(ValueError):
        build_notice_report(notices, notice, encryption_key=bytes(range(32)))


def test_finance_checklist_requires_main_verification():
    from centermanager.platform.recovery_readable_report import _review_instruction
    assert "Không tạo lại" in _review_instruction(
        {"module": "finance", "entity_type": "Income", "action": "create"}
    )
    assert "Không ghi chi hai lần" in _review_instruction(
        {"module": "finance", "entity_type": "Expense", "action": "create"}
    )
    assert "công nợ" in _review_instruction(
        {"module": "tuition", "entity_type": "Enrollment", "action": "update"}
    )


def test_wrong_key_never_exposes_unverified_event(tmp_path):
    notices, notice = _notice(tmp_path)
    key = bytes(range(32))
    event = {
        "write_session_id": "write-123",
        "event_id": "a3b3c3d3-1111-4111-8111-111111111111",
        "module": "finance", "action": "create",
        "entity_type": "Income", "entity_id": "1",
    }
    mirror_committed_payload(
        json.dumps(event).encode(), recovery_root=notices.journal.root,
        encryption_key=key,
    )
    report = build_notice_report(notices, notice, encryption_key=b"x" * 32)
    assert "CÁC THAO TÁC GHI NHẬN TRONG MIRROR: 0" in report
    assert "không đọc/xác minh được: 1" in report
    assert "UNKNOWN" in report
