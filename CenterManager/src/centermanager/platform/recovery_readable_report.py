"""User-requested plaintext *index* of committed local operations for manual review.

Do not create a plaintext copy automatically at startup. Never interpret a mirror
as proof that a transaction is absent from Git MAIN, or as a complete audit trail.
No SQLCipher restore, Git mutation, lease change, or unattended decryption.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from centermanager.platform.recovery_change_mirror import decrypt_mirrored_event

_SESSION = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_EVENT_FILE = re.compile(r"^[0-9a-fA-F-]{36}\\.enc$")
_MAX_EVENTS = 10000
_MAX_BYTES = 2 * 1024 * 1024


def build_notice_report(notices, notice: dict, *, encryption_key: bytes) -> str:
    """Produce a human-readable, conservative report from an authenticated notice.

    Caller must provide a notice returned by validate_notice() and unlock the
    local DPAPI database key. Only session-scoped authenticated AES-GCM mirrors
    are read. Unknown coverage, absent mirrors, or a malformed segment are
    never presented as zero missing business operations.
    """
    notice_path = notices.root / (str(notice.get("id", "")) + ".json")
    verified = notices.validate_notice(notice_path)
    if verified != notice:
        raise ValueError("Recovery notice was modified during report generation")
    lines = [
        "ANTECHKIDS — BÁO CÁO ĐỐI CHIẾU RECOVERY",
        "=" * 52,
        "Mã thông báo: " + verified["id"],
        "Phát hiện (UTC): " + str(verified.get("detected_at_utc", "không rõ")),
        "MAIN đã quan sát: " + str(verified.get("observed_main_oid", "không rõ")),
        "",
        "QUAN TRỌNG: Đây là danh mục sự kiện local đã được lưu trong",
        "mirror mã hóa; KHÔNG phải danh sách dữ liệu chắc chắn bị mất.",
        "Mirror có thể THIẾU sự kiện. Chưa đối chiếu nội dung với Git MAIN.",
        "Không tự nhập lại giao dịch thu/chi nếu chưa kiểm tra trùng.",
        "",
    ]
    source = verified.get("journal_file")
    session_id = None
    if source:
        journal = json.loads((notices.root / source).read_text(encoding="utf-8"))
        if not isinstance(journal, dict):
            raise ValueError("Invalid recovery journal snapshot")
        session_id = journal.get("session_id")
    if not isinstance(session_id, str) or not _SESSION.fullmatch(session_id):
        lines.extend([
            "Phiên WRITE: không xác định từ journal đã lưu.",
            "KHÔNG THỂ LIỆT KÊ SỰ KIỆN — cần kiểm tra backup mã hóa thủ công.",
        ])
        return "\n".join(lines) + "\n"

    lines.append("Phiên WRITE: " + session_id)
    root = Path(notices.journal.root) / "rv02-committed-events"
    directory = root / session_id
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError("Unsafe Recovery event directory")
    events = []
    problems = 0
    if directory.is_dir():
        paths = sorted(directory.iterdir())
        if len(paths) > _MAX_EVENTS:
            raise ValueError("Recovery event count exceeds safe report limit")
        for path in paths:
            if path.is_symlink() or not path.is_file() or not _EVENT_FILE.fullmatch(path.name):
                problems += 1
                continue
            if path.stat().st_size > _MAX_BYTES:
                problems += 1
                continue
            try:
                event = decrypt_mirrored_event(path, encryption_key=encryption_key)
                if (event.get("write_session_id") != session_id
                        or event.get("event_id", "").lower() + ".enc" != path.name.lower()):
                    raise ValueError("Event identity mismatch")
                events.append(event)
            except Exception:
                problems += 1
    events.sort(key=lambda e: (str(e.get("occurred_at_utc", "")), str(e.get("event_id", ""))))
    lines.extend(["", "CÁC THAO TÁC GHI NHẬN TRONG MIRROR: " + str(len(events))])
    if not events:
        lines.append("Không tìm thấy sự kiện giải mã được; KHÔNG có nghĩa là không có thay đổi.")
    for i, event in enumerate(events, 1):
        lines.extend([
            "",
            str(i) + ". " + str(event.get("module", "?")) + " / " + str(event.get("action", "?")),
            "   Thời gian UTC: " + str(event.get("occurred_at_utc", "?")),
            "   Đối tượng: " + str(event.get("entity_type", "?")) + " #" + str(event.get("entity_id", "?")),
            "   Người thực hiện (ID): " + str(event.get("actor_id", "?")),
            "   Mã thao tác: " + str(event.get("operation_id", "?")),
        ])
        args = event.get("summary_args_json")
        if isinstance(args, str):
            try:
                safe_args = json.loads(args)
                if isinstance(safe_args, dict):
                    for key, value in sorted(safe_args.items()):
                        if isinstance(value, (str, int, bool)):
                            lines.append("   " + key + ": " + str(value))
            except ValueError:
                problems += 1
    lines.extend([
        "",
        "TÌNH TRẠNG BẰNG CHỨNG",
        "Số phân đoạn không đọc/xác minh được: " + str(problems),
        "Mức độ đầy đủ: UNKNOWN — không được kết luận hoàn chỉnh.",
        "Báo cáo này chỉ gồm mã thao tác và ID; không có tên, số tiền hoặc",
        "giá trị cũ/mới nếu các thông tin đó không được ghi trong sự kiện.",
        "Cần dùng backup SQLCipher đã xác minh và đối chiếu MAIN để",
        "tìm giá trị nghiệp vụ; tuyệt đối không suy đoán khoản thất lạc.",
    ])
    return "\n".join(lines) + "\n"
